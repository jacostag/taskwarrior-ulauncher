import logging
import subprocess
import json
import re
import shlex
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Regular expression to check if a string is a valid UUID
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# --- Helper Functions ---

def show_error_item(title, description=""):
    logger.error("Displaying error to user: %s - %s", title, description)
    return RenderResultListAction([
        ExtensionResultItem(icon='images/icon.png', name=title, description=description, on_enter=HideWindowAction())
    ])

def is_tool_installed(name):
    try:
        subprocess.run([name, '--version'], capture_output=True, check=True, text=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("The '%s' command was not found or failed to run.", name)
        return False

# --- Listener Classes ---

class AddTaskListener:
    """Handles adding a new task."""
    def on_event(self, event, extension):
        task_description = event.get_argument()
        if not task_description:
            return show_error_item("Please enter a description for the new task.")
        command = f"task rc.confirmation=off add {task_description}"
        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png', name=f"Add task: '{task_description}'", on_enter=RunScriptAction(command))
        ])

class ListTasksListener:
    """Handles listing tasks. This is the first step."""
    def on_event(self, event, extension):
        user_filter = event.get_argument() or "+READY"
        try:
            command = ['task', user_filter, 'rc.verbose=nothing', 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)
            if not tasks: return show_error_item(f"No tasks found for filter: '{user_filter}'")

            items = []
            for task in sorted(tasks, key=lambda t: t.get('urgency', 0), reverse=True):
                if not isinstance(task, dict): continue
                try:
                    description = task['description']
                    uuid = task['uuid']
                    display_text = (description[:47] + '...') if len(description) > 50 else description
                    # This action sets the query to 'tl <uuid>', which triggers the ActionMenuListener
                    items.append(ExtensionResultItem(icon='images/icon.png', name=display_text, description="Press Enter for actions...",
                                                     on_enter=SetUserQueryAction(f"{extension.preferences['list_kw']} {uuid}")))
                except KeyError: continue
            return RenderResultListAction(items)
        except Exception as e:
            return show_error_item("An Unexpected Error Occurred", str(e))

class ActionMenuListener:
    """Handles displaying the menu of actions for a specific UUID."""
    def on_event(self, event, extension):
        uuid = event.get_argument()
        actions = [
            ExtensionResultItem(icon='images/icon.png', name="Mark as Done", on_enter=RunScriptAction(f"task {uuid} done")),
            ExtensionResultItem(icon='images/icon.png', name="Start Task", on_enter=RunScriptAction(f"task {uuid} start")),
            ExtensionResultItem(icon='images/icon.png', name="Stop Task", on_enter=RunScriptAction(f"task {uuid} stop")),
            ExtensionResultItem(icon='images/icon.png', name="Annotate Task", on_enter=SetUserQueryAction(f"{extension.preferences['annotate_kw']} {uuid} ")),
            ExtensionResultItem(icon='images/icon.png', name="Delete Task", on_enter=RunScriptAction(f"task rc.confirmation=off {uuid} delete")),
        ]
        if is_tool_installed('taskopen'):
            actions.append(ExtensionResultItem(icon='images/icon.png', name="Open Task", on_enter=RunScriptAction(f"taskopen {uuid}")))
        return RenderResultListAction(actions)

class AnnotateTaskListener:
    """Handles adding an annotation to a task."""
    def on_event(self, event, extension):
        query = event.get_argument()
        if not query or ' ' not in query:
            return show_error_item("Usage: ta <uuid> <annotation text>")
        uuid, annotation_text = query.split(' ', 1)
        safe_annotation = shlex.quote(annotation_text)
        command = f"task {uuid} annotate {safe_annotation}"
        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png', name=f"Add annotation to task {uuid[:8]}...", description=f"Note: '{annotation_text}'", on_enter=RunScriptAction(command))
        ])

# --- Main Event Router ---

class KeywordQueryEventListener:
    """Routes events to the correct listener."""
    def __init__(self):
        self.listeners = {
            "add": AddTaskListener(),
            "list": ListTasksListener(),
            "menu": ActionMenuListener(),
            "annotate": AnnotateTaskListener(),
        }

    def on_event(self, event, extension):
        if not is_tool_installed('task'):
            return show_error_item("Taskwarrior not found.")
        
        keyword = event.get_keyword()
        argument = event.get_argument() or ""

        if keyword == extension.preferences['add_kw']:
            return self.listeners["add"].on_event(event, extension)
        elif keyword == extension.preferences['annotate_kw']:
            return self.listeners["annotate"].on_event(event, extension)
        elif keyword == extension.preferences['list_kw']:
            # If the argument is a UUID, show the action menu.
            if UUID_REGEX.match(argument.strip()):
                return self.listeners["menu"].on_event(event, extension)
            # Otherwise, show the normal task list.
            else:
                return self.listeners["list"].on_event(event, extension)

class TaskwarriorExtension(Extension):
    """The main extension class."""
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
