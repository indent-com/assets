# Tools Reference

A comprehensive reference of all 31 tools available in the Indent assistant environment.

---

## 1. Read

Reads the content of any file from disk by absolute path. Supports line offsets and limits for large files, and can also read image files (PNG, JPG, etc.) for visual inspection.

**Parameters:**
- `file_path` (required) - Absolute path to the file
- `offset` (optional) - Line number to start reading from
- `limit` (optional) - Number of lines to read

---

## 2. Write

Writes content to a file on the local filesystem. Overwrites the file if it already exists. Requires the file to have been read first if it already exists.

**Parameters:**
- `file_path` (required) - Absolute path to the file
- `content` (required) - The content to write

---

## 3. Bash

Executes bash commands in a persistent shell session. Supports optional timeout and background mode for long-running processes like dev servers.

**Parameters:**
- `command` (required) - The command to execute
- `description` (required) - Short description of what the command does
- `timeout` (optional) - Timeout in seconds
- `background` (optional) - Run as a detached background process

---

## 4. Edit

Performs exact string replacements in files. Supports replacing a single occurrence, all occurrences, or a range of text defined by start and end markers.

**Parameters:**
- `file_path` (required) - Absolute path to the file
- `old_string` (required) - The text to replace
- `new_string` (required) - The replacement text
- `old_string_end` (optional) - End marker for replacing a block of text
- `replace_all` (optional) - Replace all occurrences

---

## 5. Grep

Fast file content search using ripgrep-style regexes. Results are sorted by modification time.

**Parameters:**
- `pattern` (required) - Regex pattern to search for
- `path` (optional) - Directory to search in
- `include` (optional) - File pattern to include (e.g., `*.js`)
- `multiline` (optional) - Enable multiline matching

---

## 6. Glob

Finds files using glob patterns, sorted by file modification time.

**Parameters:**
- `pattern` (required) - Glob pattern to match files
- `path` (optional) - Directory to search in

---

## 7. Agent

Launches a subagent to autonomously explore and analyze the codebase. Subagents have read-only access and cannot create their own subagents.

**Parameters:**
- `prompt` (required) - The task for the agent to perform
- `description` (required) - Short description of the task
- `agent_type` (optional) - `general-purpose`, `explore`, or `plan`

---

## 8. TodoWrite

Creates and manages a structured task list for tracking progress on multi-step tasks.

**Parameters:**
- `todos` (required) - Array of todo items, each with `id`, `content`, `status` (`pending`, `in_progress`, `completed`), and `priority` (`high`, `medium`, `low`)

---

## 9. ToolSearchToolRegex

Searches deferred tools using a regex pattern across tool names, descriptions, and parameters. Discovers tools not yet loaded into the active tool list.

**Parameters:**
- `pattern` (required) - Python regex pattern to match
- `limit` (optional) - Maximum number of results

---

## 10. DatabaseQuery

Executes SQL queries against a connected database. Results are stored by query ID and saved as Parquet files for downstream analysis.

**Parameters:**
- `query` (required) - The SQL query to execute
- `query_id` (required) - Descriptive kebab-case name for the query
- `database_id` (optional) - Database ID if multiple databases are connected

---

## 11. DatabaseGetTableSchema

Returns the complete DDL (schema definition) for a specific table, including columns, data types, partitioning, and clustering.

**Parameters:**
- `table_name` (required) - Name of the table

---

## 12. EditQuery

Edits a previously executed query by applying search-and-replace operations. The modified query is not automatically re-executed.

**Parameters:**
- `query_id` (required) - ID of a previously executed query
- `old_string` (required) - Exact string to find in the query
- `new_string` (required) - Replacement string
- `replace_all` (optional) - Replace all occurrences

---

## 13. RunQueryById

Re-executes a previously run query by its query ID. Useful for refreshing data or running an edited query.

**Parameters:**
- `query_id` (required) - ID of the query to re-run

---

## 14. CreateObservation

Records insights about database tables to improve future SQL query generation. Observations should be actionable and avoid point-in-time statistics.

**Parameters:**
- `title` (required) - Short title (max 10 words)
- `observation` (required) - 1-2 sentence insight
- `when_to_use` (required) - When this observation applies (max 10 words)
- `table_names` (optional) - Related table names

---

## 15. ReplaceTableObservation

Replaces an existing database table observation with improved content.

**Parameters:**
- `title` (required) - Updated title
- `observation` (required) - Updated observation text
- `when_to_use` (required) - When to apply
- `observation_to_replace_uuid` (required) - UUID of the observation to replace
- `table_names` (optional) - Related table names

---

## 16. ObservationSearch

Searches for existing database observations using semantic matching. Results are scored by relevance.

**Parameters:**
- `search` (required) - Search string

---

## 17. GetTableObservations

Retrieves table observations by filter criteria or specific UUIDs.

**Parameters:**
- `include_message` (required) - Whether to include observation content
- `table_name` (optional) - Filter by table name
- `limit` (optional) - Max observations to return
- `created_at_cursor` (optional) - Filter by creation time
- `observation_uuids` (optional) - Specific UUIDs to retrieve

---

## 18. GenerateVisualization

Generates data visualizations as PNG images using Python (seaborn, matplotlib, pandas). Operates on query result Parquet files.

**Parameters:**
- `code` (required) - Python code to generate the visualization
- `output_filenames` (required) - Names of output PNG files

---

## 19. GetTableNames

Returns a list of all tables in the database schema. Takes no parameters.

---

## 20. SearchDatabaseSchemas

Searches for database table schemas using semantic search powered by AI embeddings.

**Parameters:**
- `pattern` (required) - Natural language search pattern

---

## 21. CreatePR

Creates a GitHub pull request.

**Parameters:**
- `owner` (required) - GitHub org or user
- `repo` (required) - Repository name
- `title` (required) - PR title
- `body` (required) - PR description in markdown
- `head` (required) - Branch with changes
- `base` (optional) - Target branch
- `draft` (optional) - Create as draft

---

## 22. SubscribeToPR

Subscribes or unsubscribes to CI updates and PR comments for a GitHub pull request.

**Parameters:**
- `owner` (required) - GitHub org or user
- `repo` (required) - Repository name
- `pr_number` (required) - Pull request number
- `unsubscribe` (optional) - Set to true to unsubscribe

---

## 23. UploadImagePublicly

Uploads an image to public storage and returns a publicly accessible URL. Images are auto-deleted after 90 days.

**Parameters:**
- `file_path` (required) - Absolute path to the image file
- `media_type` (optional) - MIME type (auto-detected if omitted)

---

## 24. CloudCreateObservation

Records insights about the codebase that persist across sessions.

**Parameters:**
- `title` (required) - Short title (max 10 words)
- `observation` (required) - 1-2 sentence insight
- `when_to_use` (required) - When to apply (max 10 words)

---

## 25. CloudObservationSearch

Searches for existing codebase observations using semantic matching.

**Parameters:**
- `search` (required) - Search string

---

## 26. CloudReplaceObservation

Replaces an existing codebase observation with improved content.

**Parameters:**
- `title` (required) - Updated title
- `observation` (required) - Updated observation text
- `when_to_use` (required) - When to apply
- `observation_to_replace_uuid` (required) - UUID of the observation to replace

---

## 27. BuildRepositoryContainerFromCommit

Builds a container image from a specific git commit. Requires `.indent/setup/setup.sh` and `.indent/setup/verification.json` at that commit.

**Parameters:**
- `commit_sha` (required) - Full git commit SHA

---

## 28. GetBuildLogs

Retrieves build logs for a container image build. Supports pagination via offset and limit.

**Parameters:**
- `container_image_uuid` (required) - UUID of the container image
- `offset` (optional) - Starting line number
- `limit` (optional) - Max log lines to return

---

## 29. AskChat

Queries information from a previous chat session's conversation history.

**Parameters:**
- `chat_uuid` (required) - UUID of the chat to query
- `question` (required) - The question to ask

---

## 30. WebFetch

Fetches and summarizes content from a public webpage or API.

**Parameters:**
- `url` (required) - URL to retrieve
- `prompt` (required) - Prompt to extract/analyze information
- `description` (required) - Short description of what is being fetched
- `http_timeout` (optional) - Timeout in seconds

---

## 31. Skill

Executes a skill to get specialized instructions for a task. Skills are reusable capability modules that provide domain-specific guidance.

**Parameters:**
- `skill` (required) - Name of the skill to invoke
- `args` (optional) - Arguments to pass to the skill
