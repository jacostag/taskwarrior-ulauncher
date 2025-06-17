# Taskwarrior Ulauncher Extension

A Ulauncher extension for seamless interaction with Taskwarrior, allowing you to manage your tasks directly from the Ulauncher interface.

## Usage

### Add a Task

- **Keyword:** `t`
- **Action:** Any text following `t` will be added as a new task in Taskwarrior.
- **Example:** `t a new task with a +project and a tag:next`

### List Tasks

- **Keyword:** `tl`
- **Action:** Displays a list of pending tasks. You can filter by project or tags.
- **Example:** `tl` or `tl +project`

### Start/Stop a Task

- **Keyword:** `ts`
- **Action:** Toggles the active state of a task.
- **Example:** `ts 1`

### Mark Task as Done

- **Keyword:** `td`
- **Action:** Marks a task as completed.
- **Example:** `td 1`

### Annotate a Task

- **Keyword:** `ta`
- **Action:** Adds an annotation to an existing task.
- **Example:** `ta 1 This is an annotation.`

### Delete a Task

- **Keyword:** `tdel`
- **Action:** Deletes a task.
- **Example:** `tdel 1`

### Open Task with Annotations

- **Keyword:** `to`
- **Action:** Opens a task with its annotations in a text editor.
- **Example:** `to 1`
