#!/usr/bin/env python3
"""Render a message as a screenshot of the X (Twitter) composer.

Fetched at run time by the "Tweet mockups" Indent automation, which replies to every message in
Slack #tweets with the message rendered as a tweet:

  curl -fsSL https://assets.indent.com/tweetshot.py -o /tmp/tweetshot.py
  python3 /tmp/tweetshot.py --name sashank --handle sthupukari \
      --avatar "https://unavatar.io/x/sthupukari?fallback=false" \
      --text "message text" --out /tmp/tweet.png

Geometry, type and colours are matched to the original mockup: 642 css px wide at 2x device scale,
40 px avatar, Inter Tight at 16.7 px on a 20 px line. Needs google-chrome, Pillow and numpy.
"""
import argparse, base64, html, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request

FONT_CACHE = os.path.join(tempfile.gettempdir(), "tweetshot-fontface.css")

CARD_W = 642          # css px; screenshotted at 2x -> 1284 px wide
PAD_L, PAD_T, PAD_R, PAD_B = 27, 21, 50, 25
AVATAR, GAP = 40, 8
NAME_SIZE = 16.2
HANDLE_SIZE = 16.7
TEXT_SIZE = 16.7
LINE_HEIGHT = 20
TRACKING = -0.2
NAME_GAP_BOTTOM = 2
ICONS_GAP = 5

BLUE = "#4897ee"
HANDLE_COLOR = "#606c79"
BADGE_COLOR = "#4d9fec"
FALLBACK = "'Liberation Sans','Helvetica Neue',Helvetica,Arial,sans-serif"

BADGE_SVG = (
    '<svg class="badge" viewBox="0 0 22 22" aria-hidden="true">'
    '<path fill="%s" d="M20.396 11c-.018-.646-.215-1.275-.57-1.816-.354-.54-.852-.972-1.438-1.246.223-.607.27-1.264.14-1.897-.131-.634-.437-1.218-.882-1.687-.47-.445-1.053-.75-1.687-.882-.633-.13-1.29-.083-1.897.14-.273-.587-.704-1.086-1.245-1.44S11.647 1.62 11 1.604c-.646.017-1.273.213-1.813.568s-.969.854-1.24 1.44c-.608-.223-1.267-.272-1.902-.14-.635.13-1.22.436-1.69.882-.445.47-.749 1.055-.878 1.688-.13.633-.08 1.29.144 1.896-.587.274-1.087.705-1.443 1.245-.356.54-.555 1.17-.574 1.817.02.647.218 1.276.574 1.816.356.54.856.972 1.443 1.245-.224.606-.274 1.263-.144 1.896.13.634.433 1.218.877 1.688.47.443 1.054.747 1.687.878.633.132 1.29.084 1.897-.136.274.586.705 1.084 1.246 1.439.54.354 1.17.551 1.816.569.647-.016 1.276-.213 1.817-.567s.972-.854 1.245-1.44c.604.239 1.266.296 1.903.164.636-.132 1.22-.447 1.68-.907.46-.46.776-1.044.908-1.681s.075-1.299-.165-1.903c.586-.274 1.084-.705 1.439-1.246.354-.54.551-1.17.569-1.816zM9.662 14.85l-3.429-3.428 1.293-1.302 2.072 2.072 4.4-4.794 1.347 1.246z"/>'
    "</svg>" % BADGE_COLOR
)

ICONS_URI = "data:image/png;base64," + (
    "iVBORw0KGgoAAAANSUhEUgAAAUwAAAAuCAYAAABDJSC6AAAIPElEQVR42u2dXWgcVRTHf/2QEIwlxCgUsQpSfFBfxLaGLrUV"
    "H6yIyZOIFD8eLRJEWYMWNBZUlqBI0QgVCmoE9UFSq9aHUqsklvpRCvWlRFEKRdC0lGIppWnwYc5lT25md2eTney9k/ODIbOz"
    "k7k7M3f+c86595674p29YxiGYRiNWWmXwDAMwwTTMAzDBNMwDMME0zAMwwTTMAzDBNMwDMME01i2bFaLUaz7aphgGi1gCJiW"
    "Zb9a3LYhu0TR39/9wLhdisWxukWi2yHHWgUMAj8CR4FLwKxd5qCtjv0Z9ivLMiH3tVLnweyT9Xr7LTU3ATuB7cD1LTrmWeAg"
    "MAqcieR+l+SeT1rVXxgrFjHS51pgDdDpbf/J+zwqD85Fu9zBMa3WJ4ARWZ+UB6ukBNPHiWefehh9+gN4OB8APpSXeh5cBp4E"
    "DkV0nwes6i+dhdkJ9DRRAXfKMgq8KVZn6Nyco2U8C/wdiJtWT9gm1baKsh5LSiBLNYRU79NOwbzJE8sxYKpFx14P7JBjfwhs"
    "DNTStHBKGwWzW8TS5xJwRcRgD7BJljTh3APsDviaPAG8nXMZzwMfBXK+ExlFraLceCeIfer7o+pY4zXEdKnZqcTyUeBwi4//"
    "JfC5lLET2BVgfS57L7KSiGgFI1fB7BHB1JwHLgAzattu7/gvk8Q1HYMkcc/hAlndC7HSY2WSeGJg25VleTiH4x+WY++QskIT"
    "zCHvheas/rIJZr7i0O2J5X/AOU8o05gRAX0DOABskO3PijUaoqW5DzidcxmHrOotCa6BZyrHMqa8skJhs7IuR0QgtXcwjsUy"
    "cxHMTs8Nv8DcIHIWZuQNPCxi6SzNiZze/CZoRiOeAtYBvwJfF+zchpjbUFdR3sGIfFcS0QypN0MhBNO3LKcXUd4wSWzTWZrl"
    "QAXTKDb7gEfU51eB9wpwXpuVGDr6vX0q6tnTDXdZY9kmmHW4lrnxtnMtKPNN4AtZ30DS7SM0i+4Z8uvUPwu8b1WvbWxSYnkK"
    "uF28nlgFM00ktRuehhZN97ec4f9MMBt8v0atn6dxzDILPwDHqLaivxCYYA4Cr+RcRhfVPo9G++r8vyKYHRGfT9rAgyz9XytU"
    "u4tp971M0vthwKrKfFY2+E5blxdaWK5+g20grCGaUySd7PNcpqzqtY1JqmEgZ5W9G/H5TKRsy9qlyxdLx1GrJs1bmPqte6lF"
    "1qW2Mn+mGsvcSjixzIPALVY1Cs3TwOPAHSIOn0V8LgNUW799F7uWe53mxruRXjHEMW+XsEqHaMkPNfa7C3hY1r8CTtbY7x7g"
    "QZJRW1+ShGqaFkz93ZUcTno2o6VrGK3mIvBBne/9Mfahi4nrG+u72GnudWzn5nMr8L3Sp+eAx5gf1rsL+E59fgHYliKaDwCf"
    "evvdC/zVrEu+qoa45cE19gwbgTDO/LhgSbbFMMywAvRSjZG7hBtp7nq/iOlkyjWYJsyUcAMilqeB47LtoZT9nGX5myx6m8b9"
    "73E55mrqxG/badkdU+sb7Dk12oxLcae72fQzt3GuTDzp7ipU45tldY66NXyyxnWol3RlWVNPMK/mLKx6rPmPEV/D+2UpCsst"
    "gfBmsai0OIwoy8u32JyQxCCa2sr0xTLWrkNfkbSnrAPulm3f1NgP4E5Z9DaN+9+75ZgzNfYD6scwZ3J2mVcuocufF3eQJF9w"
    "D96piK2rPmq3ro5QzI7NfitxvXherb6LRwI+v0mqSTfSRv6kUfbc99DyZ/4O3Ee10edb4JeU/U6SxCwbNfocEk9iG9VGn98X"
    "IpiX1Xqn7NuqlvItnht+JNIH7hrvGsVIicbdULJ2bK7ViTpEq9L/nVmsrrS+i1sjsDJLKVZnrReIfnk4oQ3tRXmKbP2YT1K7"
    "Zdx/sWQ6x3qu9ixzc1d2tfCEdSUbxbKyh4CL2fWLC+ridyMp4ummrhiXh2ycamNJKXC3b8j7ne68m/mtaW566FZmM2GJEc+d"
    "H8fmBGpoYULSWd1ZTt0kY8lnWlDmYEb3IERuVJblWrV9LcnIEWedT0d0TlkTCKe5bKUaVk1o93WhVmUj4byBJJFHLFQaXJMJ"
    "tY9O1FFSIrpsh042EsyLYmV2ijXaA/yzyDIPeNZlTFNXPEKSuCGNj73PTxJHFpxmEwhr8exLEcoQ45zbgNe8c27Vb/0zgns8"
    "IPdswrO0yw1edGlxW3ffB0ww0zmvrMwucZ8Xaj0NE3fs8rom9u0ucL2JzcLYGrj124571tfEC9VvECyxTMkimJdIshS5nJhr"
    "xNrMkkDYsQV4yRPLPcSX2u0Tkvl4XOz3NuB1Wd8F/CHrM8TbkFVUbPKvdKvTT7yhxTWtFwEs48QxWTOunxeR6FaWZpeIZr24"
    "5hZ5uw9620Of16ceWuS1pX0MOGHPYVCcJUlROEYyhC4P1quyYrQ604ZT+h3eIYwZQNtOMx3SzzE/H2YPSWfPtSSthj2yDJMk"
    "sfiiYGJpxMVB+buDfAYX3C/H1mXF6q73ekKp3e5eE8vmLExtaV5m/jS7nczth9jB/OGOP4spbxnWjaVilKQFu4NkgEEe0+wi"
    "z8RoAa6X67Opez9Y3tZFCCYkMc0z4uqsIb3D9nH19yrwFsWcJ+cE8KJaN8LiDElvBTc3+Y4cyrgsZZwpwPXSI4O09WksQjAd"
    "LhnuSqmMq6lmOPqWZB7oIxS/U/o+q0ZBcwjYSDJv+HZaN7vjWXHDRwsilr6VadZlCive2TtmV2F54vIi2hwuho9rzOy1S9E6"
    "C9OI3/2ylk8jjV5sKGQqluncRNMwrG6YYBqGYZhgGoZhmGAahmGYYBqGYZhgGoZhmGAahmEYHv8DY2jrZ0Dm82sAAAAASUVO"
    "RK5CYII="
)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url, timeout=45):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout
    ).read()


def font_css(text=""):
    """Google-hosted Inter Tight (+ any emoji the text needs), inlined as data URIs."""
    css_parts = []
    if os.path.exists(FONT_CACHE):
        css_parts.append(open(FONT_CACHE).read())
    else:
        block = inline_faces("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;700&display=swap",
                             latin_only=True)
        open(FONT_CACHE, "w").write(block)
        css_parts.append(block)
    glyphs = "".join(sorted({c for c in text if ord(c) > 0x2000 and not c.isspace()}))
    if glyphs:
        try:
            css_parts.append(inline_faces(
                "https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&text="
                + urllib.parse.quote(glyphs), latin_only=False))
        except Exception as exc:
            print("emoji font unavailable: %s" % exc, file=sys.stderr)
    return "\n".join(css_parts)


def inline_faces(css_url, latin_only):
    css = fetch(css_url).decode()
    out = []
    for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
        rng = re.search(r"unicode-range:\s*([^;]+);", block)
        if latin_only and rng and not re.match(r"\s*U\+0{0,3}0-|\s*U\+0100-02BA", rng.group(1)):
            continue
        url = re.search(r"url\((https://[^)]+)\)", block)
        if not url:
            continue
        blob = base64.b64encode(fetch(url.group(1))).decode()
        out.append(block.replace(url.group(1), "data:font/woff2;base64," + blob))
    return "\n".join(out)


def slack_to_text(raw):
    """Slack markup -> the plain text a reader sees."""
    t = raw
    t = re.sub(r"<@[UWB][A-Z0-9]+\|([^>]+)>", r"@\1", t)
    t = re.sub(r"<@[UWB][A-Z0-9]+>", "", t)
    t = re.sub(r"<#C[A-Z0-9]+\|([^>]+)>", r"#\1", t)
    t = re.sub(r"<!(here|channel|everyone)\|?[^>]*>", r"@\1", t)
    t = re.sub(r"<((?:https?|mailto):[^|>]+)\|([^>]+)>", r"\2", t)
    t = re.sub(r"<((?:https?|mailto):[^>]+)>", r"\1", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def text_html(text):
    out, token = [], re.compile(r"(https?://\S+|[@#][A-Za-z0-9_]+)")
    for part in token.split(text):
        if not part:
            continue
        if token.fullmatch(part):
            out.append('<span class="lk">%s</span>' % html.escape(part))
        else:
            out.append(html.escape(part).replace("\n", "<br>"))
    return "".join(out)


def data_uri(src):
    blob = fetch(src) if src.startswith("http") else open(src, "rb").read()
    kind = "png" if blob[:4] == b"\x89PNG" else "jpeg"
    return "data:image/%s;base64,%s" % (kind, base64.b64encode(blob).decode())


def avatar_uri(candidates, name):
    """First candidate URL/path that resolves; otherwise an initial-on-gradient circle."""
    for src in candidates:
        if not src:
            continue
        try:
            return data_uri(src)
        except Exception as exc:
            print("avatar %s unavailable: %s" % (src, exc), file=sys.stderr)
    letter = html.escape((name.strip()[:1] or "?").upper())
    hue = sum(ord(c) for c in name) % 360
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'>"
        "<rect width='80' height='80' fill='hsl(%d,62%%,58%%)'/>"
        "<text x='40' y='55' font-family='Inter Tight,Liberation Sans,sans-serif' font-size='40' "
        "font-weight='700' fill='#fff' text-anchor='middle'>%s</text></svg>" % (hue, letter)
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def build_html(name, handle, avatar, text, icons, verified=True):
    return f"""<!doctype html><meta charset="utf-8"><style>
{font_css(text)}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ background:#ff00ff; }}
body {{ -webkit-font-smoothing:antialiased; }}
.card {{ width:{CARD_W}px; background:#fff; display:flex; gap:{GAP}px;
  padding:{PAD_T}px {PAD_R}px {PAD_B}px {PAD_L}px;
  font-family:'Inter Tight','Noto Color Emoji',{FALLBACK}; }}
.avatar {{ width:{AVATAR}px; height:{AVATAR}px; border-radius:50%; object-fit:cover; flex:0 0 auto; }}
.col {{ flex:1 1 auto; min-width:0; }}
.head {{ display:flex; align-items:center; gap:3px; margin-bottom:{NAME_GAP_BOTTOM}px; }}
.name {{ font-size:{NAME_SIZE}px; font-weight:700; color:#000; letter-spacing:{TRACKING}px; }}
.badge {{ width:18px; height:18px; display:block; flex:0 0 auto; }}
.handle {{ font-size:{HANDLE_SIZE}px; color:{HANDLE_COLOR}; letter-spacing:{TRACKING}px; }}
.text {{ font-size:{TEXT_SIZE}px; line-height:{LINE_HEIGHT}px; color:#000; letter-spacing:{TRACKING}px;
  white-space:pre-wrap; overflow-wrap:break-word; }}
.lk {{ color:{BLUE}; }}
.caret {{ display:inline-block; width:1px; height:{LINE_HEIGHT}px; background:{BLUE};
  vertical-align:-5px; }}
.icons {{ margin-top:{ICONS_GAP}px; display:flex; justify-content:flex-end; }}
.icons img {{ width:166px; height:23px; display:block; }}
</style>
<div class="card">
  <img class="avatar" src="{avatar}">
  <div class="col">
    <div class="head"><span class="name">{html.escape(name)}</span>{BADGE_SVG if verified else ''}<span class="handle">@{html.escape(handle)}</span></div>
    <div class="text">{text_html(text)}<span class="caret"></span></div>
    <div class="icons"><img src="{icons}"></div>
  </div>
</div>"""


def screenshot(doc, out_path):
    from PIL import Image
    import numpy as np
    with tempfile.TemporaryDirectory() as td:
        page, shot = os.path.join(td, "p.html"), os.path.join(td, "s.png")
        open(page, "w").write(doc)
        subprocess.run(
            ["google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
             "--hide-scrollbars", "--force-device-scale-factor=2",
             "--window-size=%d,2400" % (CARD_W + 40), "--virtual-time-budget=10000",
             "--screenshot=" + shot, "file://" + page],
            check=True, capture_output=True, timeout=180)
        a = np.array(Image.open(shot).convert("RGB"))
        keep = ~((a[:, :, 0] > 240) & (a[:, :, 1] < 40) & (a[:, :, 2] > 240))
        rows, cols = np.where(keep.any(axis=1))[0], np.where(keep.any(axis=0))[0]
        Image.open(shot).convert("RGB").crop(
            (cols.min(), rows.min(), cols.max() + 1, rows.max() + 1)).save(out_path)
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--handle", required=True)
    p.add_argument("--avatar", required=True,
                   help="comma-separated candidate image URLs/paths, tried in order")
    p.add_argument("--text", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--no-badge", action="store_true")
    a = p.parse_args()
    doc = build_html(a.name, a.handle.lstrip("@"), avatar_uri(a.avatar.split(","), a.name),
                     slack_to_text(a.text), ICONS_URI, not a.no_badge)
    print(screenshot(doc, a.out))


if __name__ == "__main__":
    main()
