#!/usr/bin/env python3
"""Token-waste analyzer for one user's Indent sessions over a time window.

  waste.py sql <user_id> <org_id> [hours]            -> prints the three SQL queries (A, B, C) to run with run_query
  waste.py report <A.parquet> <B.parquet> <C.parquet> -> prints a markdown report; writes traj/<session>.md spines

Prod read-replica tables: sessions, billable_events (indexed on organization_id, occurred_at), session_events.
Cost comes from session_events completion_ended.costNanodollars (billable_events cost columns are 0 for some models).
"""
import sys, re, os, bisect, warnings
warnings.filterwarnings("ignore")

FAM = """with active as (
  select distinct session_id from billable_events
  where organization_id = '{org}' and deleted_at is null and occurred_at > now() - interval '{h} hours'
), fam as (
  select s.id, coalesce(s.root_session_id, s.id) root_id, s.title, s.model, s.created_at, s.source->>'kind' src, s.is_private
  from sessions s join active a on a.session_id = s.id
  where s.deleted_at is null and s.created_by->>'id' = '{user}'
)"""
SQL_A = FAM + """, ev as (
  select e.session_id, e.type, e.role, e.created_at, e.body->'output'->>'kind' kind,
    (e.body->'usage'->>'inputTokens')::bigint inp, (e.body->'usage'->>'outputTokens')::bigint outp,
    (e.body->'usage'->>'cacheReadTokens')::bigint cr, (e.body->'usage'->>'cacheCreationTokens')::bigint cc
  from fam f join session_events e on e.session_id = f.id
  where e.deleted_at is null and e.created_at > now() - interval '{h} hours'
    and e.type in ('tool_call','tool_call_result','text','completion_ended','compact','child_session_spawned','error')
)
select f.root_id, f.id session_id, f.title, f.model, f.src, f.is_private, f.created_at,
  min(ev.created_at) first_ev, max(ev.created_at) last_ev,
  count(*) filter (where type='completion_ended') completions,
  coalesce(sum(inp),0) inp, coalesce(sum(outp),0) outp, coalesce(sum(cr),0) cr, coalesce(sum(cc),0) cc,
  count(*) filter (where type='tool_call') tool_calls,
  count(*) filter (where type='compact') compactions,
  count(*) filter (where type='child_session_spawned') children
from fam f left join ev on ev.session_id = f.id
group by 1,2,3,4,5,6,7 order by f.root_id, f.created_at"""
SQL_B = FAM + """
select f.root_id, e.session_id, e.sequence, e.created_at, e.type,
  case e.type when 'tool_call' then e.body->'call'->>'name' else e.body->'output'->>'kind' end k,
  e.body->>'toolCallId' cid,
  case e.type when 'tool_call' then md5((e.body->'call'->'input')::text) end h,
  case when e.type = 'tool_call' then left(coalesce(e.body->'call'->'input'->>'command', e.body->'call'->'input'->>'path', e.body->'call'->'input'->>'description', e.body->'call'->'input'->>'title', e.body->'call'->'input'->>'sql', e.body->'call'->'input'->>'pattern', e.body->'call'->'input'->>'session'), 140)
       when e.body->'output'->>'kind' <> 'ok' then left(e.body->'output'->>'content', 200)
       else left(e.body->'output'->'result'->'value'->>'outcome', 12) || ':' || coalesce(e.body->'output'->'result'->'value'->>'exitCode','') end v,
  length(e.body::text) blen
from fam f join session_events e on e.session_id = f.id
where e.deleted_at is null and e.created_at > now() - interval '{h} hours' and e.type in ('tool_call','tool_call_result')
order by e.session_id, e.sequence"""
SQL_C = FAM + """
select f.root_id, e.session_id, e.sequence, e.created_at, e.role, e.type,
  case e.type
    when 'text' then left(e.body->>'text', case when e.role='user' then 1500 else 700 end)
    when 'thinking' then left(e.body->>'text', 200)
    when 'tool_call' then left(e.body->'call'->'input'->>'message', 500)
    when 'compact' then 'COMPACT'
    when 'error' then left(e.body::text, 400)
    when 'completion_ended' then (e.body->'usage'->>'inputTokens') || '/' || (e.body->'usage'->>'cacheReadTokens') || '/' || (e.body->'usage'->>'cacheCreationTokens') || '/' || (e.body->'usage'->>'outputTokens') || '/' || coalesce(e.body->>'costNanodollars','0')
  end v
from fam f join session_events e on e.session_id = f.id
where e.deleted_at is null and e.created_at > now() - interval '{h} hours'
  and (e.type in ('text','thinking','compact','error','completion_ended') or (e.type='tool_call' and e.body->'call'->>'name' in ('respond','ask_user_question')))
order by e.session_id, e.sequence"""

if len(sys.argv) > 1 and sys.argv[1] == "sql":
    user, org = sys.argv[2], sys.argv[3]
    h = sys.argv[4] if len(sys.argv) > 4 else "24"
    for name, q in (("A", SQL_A), ("B", SQL_B), ("C", SQL_C)):
        print(f"-- ===== QUERY {name} =====\n" + q.format(user=user, org=org, h=h) + "\n")
    sys.exit(0)
if len(sys.argv) != 5 or sys.argv[1] != "report":
    print(__doc__); sys.exit(2)

import pandas as pd, pyarrow.parquet as pq
A, B, C = [pq.read_table(p).to_pandas() for p in sys.argv[2:5]]
link = lambda s: f"https://app.indent.com/c/{s}"
A = A[A.completions > 0].copy()
for c in ["inp", "outp", "cr", "cc"]:
    A[c] = A[c].astype("int64")
A["is_root"] = A.session_id == A.root_id
title = A[A.is_root].set_index("root_id").title.to_dict()
for r in A.root_id.unique():
    title.setdefault(r, A[A.root_id == r].title.iloc[0] + " (child only)")
rt = A.set_index("session_id").root_id.to_dict()
ttl = lambda sid: title.get(rt.get(sid, sid), "?")

# ---- completions (C): context size, cost, cache misses
C = C.sort_values(["session_id", "sequence"])
comp = C[C.type == "completion_ended"].copy()
parts = comp.v.str.split("/", expand=True).astype("int64")
comp["ctx"] = parts[0] + parts[1] + parts[2]
comp["cost"] = parts[4] / 1e9
comp["cache_miss"] = (parts[1] == 0) & (parts[0] + parts[2] > 20000)
A = A.merge(comp.groupby("session_id").agg(usd=("cost", "sum"), max_ctx=("ctx", "max"),
    cache_miss=("cache_miss", "sum"), cache_miss_cost=("cost", lambda s: s[comp.loc[s.index, "cache_miss"]].sum()),
    tail_cost=("cost", lambda s: s[comp.loc[s.index, "ctx"] > 120000].sum())).reset_index(), on="session_id", how="left").fillna({"usd": 0, "max_ctx": 0, "cache_miss": 0, "cache_miss_cost": 0, "tail_cost": 0})

# ---- tool calls (B): pair calls with results by toolCallId; each call is charged the completion that consumed its result
calls = B[B.type == "tool_call"].rename(columns={"k": "tool", "blen": "in_len"})
res = B[B.type == "tool_call_result"].rename(columns={"k": "kind", "blen": "out_len", "v": "rv"})[["session_id", "cid", "kind", "out_len", "rv"]].drop_duplicates(["session_id", "cid"])
B = calls.merge(res, on=["session_id", "cid"], how="left").sort_values(["session_id", "sequence"]).copy()
B["rv"] = B.rv.fillna(""); B["v"] = B.v.fillna(""); B["out_len"] = B.out_len.fillna(0)
B["failed"] = (B.kind != "ok") | (B.tool.eq("bash") & B.rv.str.contains(r"COMPLETED:(?!0$)\d+|TIMED_OUT", regex=True))
nc = {}
for sid, g in comp.groupby("session_id"):
    seqs, costs = list(g.sequence), list(g.cost)
    for s in B.sequence[B.session_id == sid]:
        i = bisect.bisect_right(seqs, s); nc[(sid, s)] = costs[i] if i < len(costs) else 0.0
B["react_cost"] = [nc.get(k, 0.0) for k in zip(B.session_id, B.sequence)]
B["dup"] = B.duplicated(["session_id", "h"], keep="first")
streak, prev, n = [], None, 0
for r in B.itertuples():
    key = (r.session_id, r.tool)
    n = (n + 1 if prev == key else 1) if r.failed else 0
    prev = key if r.failed else None
    streak.append(n)
B["streak"] = streak
VERIFY = r"vitest|typecheck|tsc\b|pnpm (?:run )?(?:test|lint|check|fmt|format)|bin/fmt|bin/lint|bin/check|eslint|oxlint|pytest|cargo (?:test|check)|go test"
B["verify"] = B.tool.eq("bash") & B.v.str.contains(VERIFY, regex=True)
B["edit"] = B.tool.isin(["edit", "apply_patch", "write"])
B["big_out"] = B.out_len.fillna(0) > 12000
B["mem_miss"] = B.tool.eq("read") & B.failed & B.v.str.contains("/.indent/memories/")
B["dnr"] = B.tool.eq("do_not_respond")
def bash_class(r):
    if r.tool != "bash" or not r.failed: return None
    rv, v = r.rv, r.v
    if "TIMED_OUT" in rv: return "bash timed out"
    if rv.endswith((":143", ":137")): return "killed (SIGTERM/OOM 143/137)"
    if rv.endswith(":127"): return "command not found (127): pnpm/tools without direnv"
    if rv.endswith((":128", ":129")) and re.match(r"\s*(git|gh)\b", v): return "git/gh run outside the repo cwd (128/129)"
    if rv.endswith((":1", ":2")) and re.match(r"\s*(cd [^&]+&& )?(rg|grep|fd)\b", v): return "rg/grep no match (1/2)"
    if rv.endswith(":2"): return "usage/arg error (2)"
    return "real failure (tests/typecheck/build)"
B["bclass"] = [bash_class(r) for r in B.itertuples()]

# ---- user messages and cost per prompt (completions until the next human message)
U = C[(C.type == "text") & (C.role == "user")].copy()
U["v"] = U.v.fillna("")
MACHINE = r"^(All CI checks|PR #\d+ was|New commits were pushed|<pr_comment>|<ci_|## Fix PR Review|<slack_message|<message user=\"indent)"
U["machine"] = U.v.str.contains(MACHINE, regex=True)
U["words"] = U.v.str.split().str.len()
U["correction"] = U.v.str.strip().str.contains(r"^(?:no\b|nope|not that|that'?s not|wrong|i meant|i said|again\b|still\b|didn'?t work|doesn'?t work|revert|undo|why did you|why didn'?t|don'?t|stop\b|wait\b|actually)", regex=True, case=False)
rows = []
for sid, g in U.groupby("session_id"):
    cs = comp[comp.session_id == sid]; seqs = list(g.sequence) + [10**12]
    for i, r in enumerate(g.itertuples()):
        c = cs[(cs.sequence > r.sequence) & (cs.sequence < seqs[i + 1])]
        rows.append(dict(session_id=sid, sequence=r.sequence, text=r.v[:220].replace("\n", " "), cost=c.cost.sum(), turns=len(c), machine=r.machine, correction=r.correction))
T = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["session_id", "sequence", "text", "cost", "turns", "machine", "correction"])

# ---- per session + per chat
def sm(sid):
    b = B[B.session_id == sid]; u = U[U.session_id == sid]
    return dict(calls=len(b), failed=int(b.failed.sum()), fail_cost=b.react_cost[b.failed].sum(), dups=int(b.dup.sum()), dup_cost=b.react_cost[b.dup].sum(),
        verify=int(b.verify.sum()), edits=int(b.edit.sum()), big_out_kb=int(b.out_len[b.big_out].sum() / 1000), user_msgs=int((~u.machine).sum()), corrections=int(u.correction.sum()))
A = A.merge(pd.DataFrame([dict(session_id=s, **sm(s)) for s in A.session_id]), on="session_id")
fam = A.groupby("root_id").agg(usd=("usd", "sum"), sessions=("session_id", "count"), completions=("completions", "sum"), failed=("failed", "sum"),
    fail_cost=("fail_cost", "sum"), dups=("dups", "sum"), dup_cost=("dup_cost", "sum"), compacts=("compactions", "sum"), tail_cost=("tail_cost", "sum"),
    user_msgs=("user_msgs", "sum"), corrections=("corrections", "sum")).sort_values("usd", ascending=False)
fam["child_usd"] = [A[(A.root_id == r) & (~A.is_root)].usd.sum() for r in fam.index]
total = max(fam.usd.sum(), 0.01)

out = []; p = out.append
p(f"## Totals: ${total:.2f}, {len(fam)} chats, {len(A)} sessions, {int(A.completions.sum())} completions, {int(A.cr.sum())/1e6:.0f}M cache-read tok, {int((~U.machine).sum())} human messages")
p(f"- failed tool calls: {int(A.failed.sum())}, reaction turns ${A.fail_cost.sum():.2f}")
p(f"- identical tool calls re-run: {int(A.dups.sum())} (${A.dup_cost.sum():.2f})")
p(f"- turns at context >120k: ${A.tail_cost.sum():.2f} ({A.tail_cost.sum()/total*100:.0f}% of spend); compactions: {int(A.compactions.sum())}; cache misses {int(A.cache_miss.sum())} (${A.cache_miss_cost.sum():.2f})")
p(f"- subagents: {int((~A.is_root).sum())} children, ${fam.child_usd.sum():.2f} ({fam.child_usd.sum()/total*100:.0f}%)")
p(f"- verification runs (test/typecheck/lint/fmt): {int(A.verify.sum())} vs edits: {int(A.edits.sum())}")
dnr = B[B.dnr]; mm = B[B.mem_miss]; mt = T[T.machine]
p(f"- machine-triggered turns (CI/PR/review-bot events): {len(mt)} for ${mt.cost.sum():.2f}; do_not_respond wake-ups: {len(dnr)} for ${dnr.react_cost.sum():.2f}")
if len(mm): p(f"- reads of memory files that do not exist: {len(mm)} (${mm.react_cost.sum():.2f})")
p("")
p("## Bash failures by class")
for k, g in B[B.bclass.notna()].groupby("bclass").agg(n=("sequence", "size"), cost=("react_cost", "sum")).sort_values("n", ascending=False).iterrows():
    p(f"- {int(g.n)}x ${g.cost:.2f} {k}")
p("")
p("## Most expensive prompts (spend until the next human message)")
for r in T[~T.machine].sort_values("cost", ascending=False).head(10).itertuples():
    p(f"- ${r.cost:.2f} / {r.turns} completions [{ttl(r.session_id)[:30]}]({link(r.session_id)}): {r.text[:150]!r}")
p("")
p("## Chats by spend")
p("| $ | chat | sess | compl | msgs | fails ($) | dups ($) | ctx>120k $ | compacts | subagent $ |")
p("|--:|---|--:|--:|--:|--|--|--:|--:|--:|")
for r, f in fam.head(12).iterrows():
    p(f"| {f.usd:.2f} | [{title.get(r,'?')[:38]}]({link(r)}) | {int(f.sessions)} | {int(f.completions)} | {int(f.user_msgs)} | {int(f.failed)} (${f.fail_cost:.2f}) | {int(f.dups)} (${f.dup_cost:.2f}) | {f.tail_cost:.2f} | {int(f.compacts)} | {f.child_usd:.2f} |")
p("")
rep = A[A.is_root].groupby("title").session_id.apply(list); rep = rep[rep.str.len() > 1]
if len(rep):
    p("## Same title, several chats (restarts)")
    for t, ids in rep.items():
        p(f"- {t}: " + ", ".join(f"[{i[:8]}]({link(i)}) ${A[A.session_id==i].usd.iloc[0]:.2f}" for i in ids))
    p("")
F = B[B.failed & (B.tool != "bash")].copy(); F["sig"] = F.tool + ": " + F.rv.str.slice(0, 100)
if len(F):
    p("## Non-bash tool failures")
    for sig, g in F.groupby("sig").agg(n=("sequence", "size"), cost=("react_cost", "sum")).sort_values("n", ascending=False).head(10).iterrows():
        p(f"- {int(g.n)}x ${g.cost:.2f} `{sig}`")
    p("")
ST = B[B.streak >= 3]
if len(ST):
    p("## Failure streaks (>=3 consecutive on one tool)")
    for (sid, tool), g in ST.groupby(["session_id", "tool"]):
        p(f"- [{ttl(sid)[:40]}]({link(sid)}) {tool} x{int(g.streak.max())}: `{g.rv.iloc[-1][:110]}` `{g.v.iloc[-1][:80]}`")
    p("")
D = B[B.dup & ~B.dnr]
if len(D):
    p("## Most re-run identical calls")
    for (sid, tool, v), n in D.groupby(["session_id", "tool", D.v.str.slice(0, 80)]).size().sort_values(ascending=False).head(8).items():
        p(f"- {n}x {tool} `{v}` in [{ttl(sid)[:30]}]({link(sid)})")
    p("")
BO = B[B.big_out].sort_values("out_len", ascending=False)
if len(BO):
    p("## Largest tool outputs pulled into context")
    for r in BO.head(8).itertuples():
        p(f"- {int(r.out_len/1000)}KB {r.tool} `{r.v[:90]}` [{ttl(r.session_id)[:30]}]({link(r.session_id)})")
    p("")
cor = T[T.correction & ~T.machine]
if len(cor):
    p("## Re-steers by the user (and what the rework cost)")
    for r in cor.sort_values("cost", ascending=False).head(10).itertuples():
        p(f"- ${r.cost:.2f} [{ttl(r.session_id)[:30]}]({link(r.session_id)}): {r.text[:160]!r}")
    p("")
SA = A[~A.is_root].groupby("root_id").agg(n=("session_id", "count"), usd=("usd", "sum"), compl=("completions", "sum"))
if len(SA):
    p("## Subagent fan-out")
    for r, g in SA.sort_values("usd", ascending=False).head(6).iterrows():
        p(f"- [{title.get(r,'?')[:40]}]({link(r)}): {int(g.n)} children, ${g.usd:.2f}, {int(g.compl)} completions")
    p("")

os.makedirs("traj", exist_ok=True)
for sid in A.sort_values("usd", ascending=False).head(6).session_id:
    rows = []
    for r in C[C.session_id == sid].itertuples():
        if r.type == "completion_ended" or (r.type == "thinking" and (not r.v or (r.v.startswith("**") and len(r.v) < 80))): continue
        rows.append((r.sequence, f"[{r.sequence}] {r.role}/{r.type}: {r.v}"))
    for r in B[B.session_id == sid].itertuples():
        rows.append((r.sequence, f"[{r.sequence}] tool {'FAIL ' if r.failed else ''}{r.tool} ({int(r.out_len or 0)}B, ${r.react_cost:.3f}): {r.v}" + (f" -> {r.rv}" if r.failed else "")))
    a = A[A.session_id == sid].iloc[0]
    with open(f"traj/{sid}.md", "w") as fh:
        fh.write(f"# {a.title} ${a.usd:.2f} {a.completions} completions max_ctx={int(a.max_ctx)} {link(sid)}\n\n" + "\n".join(s for _, s in sorted(rows)))
print("\n".join(out))
