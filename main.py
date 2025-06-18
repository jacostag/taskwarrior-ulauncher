import logging
import subprocess
import json
import re
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction

# Set up logging so we can see what's happening in the Ulauncher logs.
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Regular expression to check if a string is a valid UUID
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# --- Helper Functions ---

def show_error_item(title, description=""):
    """Creates a Ulauncher item to display an error message."""
    logger.error("Displaying error to user: %s - %s", title, description)
    return RenderResultListAction([
        ExtensionResultItem(
            icon='images/icon.png',
            name=title,
            description=description,
            on_enter=HideWindowAction()
        )
    ])

def is_tool_installed(name):
    """Checks if a command-line tool is available (e.g., 'task' or 'taskopen')."""
    try:
        subprocess.run([name, '--version'], capture_output=True, check=True, text=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("The '%s' command was not found or failed to run.", name)
        return False

# --- Individual Action Listeners ---

class AddTaskListener:
    """Handles the 'add task' keyword query. (Working and unchanged)"""
    def on_event(self, event, extension):
        task_description = event.get_argument()
        if not task_description:
            return show_error_item("Please enter a description for the new task.")
        
        command = f"task rc.confirmation=off add {task_description}"
        return RenderResultListAction([
            ExtensionResultItem(
                icon='images/icon.png',
                name=f"Add task: '{task_description}'",
                description="Press Enter to add this task to Taskwarrior",
                on_enter=RunScriptAction(command)
            )
        ])

class ListTasksListener:
    """
    Handles listing tasks.
    (UPDATED to trigger the action menu when a task is selected)
    """
    def on_event(self, event, extension):
        user_filter = event.get_argument() or "+READY"
        try:
            command = ['task', user_filter, 'rc.verbose=nothing', 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)

            if not tasks:
                return show_error_item(f"No tasks found for filter: '{user_filter}'")

            items = []
            for task in sorted(tasks, key=lambda t: t.get('urgency', 0), reverse=True):
                if not isinstance(task, dict): continue
                try:
                    description = task['description']
                    uuid = task['uuid']
                    display_text = (description[:47] + '...') if len(description) > 50 else description
                    
                    items.append(
                        ExtensionResultItem(
                            icon='images/icon.png',
                            name=display_text,
                            description="Press Enter to see actions for this task...",
                            # NEW BEHAVIOR: When user presses Enter, set the query to "tl <uuid>"
                            # This will trigger our new TaskActionMenuListener.
                            on_enter=SetUserQueryAction(f"{extension.preferences['list_kw']} {uuid}")
                        )
                    )
                except KeyError:
                    continue # Skip malformed tasks
            
            return RenderResultListAction(items)
        except Exception as e:
            return show_error_item("An Unexpected Error Occurred", str(e))

class TaskActionMenuListener:
    """
    (NEW) Displays the menu of actions for a selected task UUID.
    """
    def on_event(self, event, extension):
        uuid = event.get_argument()
        
        # Build the list of actions for the given UUID
        actions = [
            ExtensionResultItem(icon='images/icon.png', name=f"Mark as Done", description=f"Mark task {uuid[:8]}... as done", on_enter=RunScriptAction(f"task {uuid} done")),
            ExtensionResultItem(icon='images/icon.png', name=f"Start Task", description=f"Start tracking task {uuid[:8]}...", on_enter=RunScriptAction(f"task {uuid} start")),
            ExtensionResultItem(icon='images/icon.png', name=f"Stop Task", description=f"Stop tracking task {uuid[:8]}...", on_enter=RunScriptAction(f"task {uuid} stop")),
            ExtensionResultItem(icon='images/icon.png', name=f"Annotate Task", description=f"Add a note to task {uuid[:8]}...", on_enter=SetUserQueryAction(f"{extension.preferences['annotate_kw']} {uuid} ")),
            ExtensionResultItem(icon='images/gavel.png', name=f"Delete Task", description=f"Permanently delete task {uuid[:8]}...", on_enter=RunScriptAction(f"task rc.confirmation=off {uuid} delete")),
        ]
        
        # Add the 'taskopen' action only if the tool is installed
        if is_tool_installed('taskopen'):
            actions.append(ExtensionResultItem(icon='images/icon.png', name=f"Open Task", description=f"Open task {uuid[:8]}... with taskopen", on_enter=RunScriptAction(f"taskopen {uuid}")))

        return RenderResultListAction(actions)

class AnnotateTaskListener:
    """
    (NEW) Handles adding an annotation to a task.
    """
    def on_event(self, event, extension):
        query = event.get_argument()
        if not query or ' ' not in query:
            return show_error_item("Usage: ta <uuid> <annotation text>")
            
        uuid, annotation_text = query.split(' ', 1)

        # Use shell quoting to handle special characters in the annotation
        import shlex
        safe_annotation = shlex.quote(annotation_text)

        command = f"task {uuid} annotate {safe_annotation}"

        return RenderResultListAction([
            ExtensionResultItem(
                icon='images/icon.png',
                name=f"Add annotation to task {uuid[:8]}...",
                description=f"Note: '{annotation_text}'",
                on_enter=RunScriptAction(command)
            )
        ])

# --- Main Event Router (UPDATED) ---

class KeywordQueryEventListener:
    """Routes events to the correct listener."""
    def __init__(self):
        self.add_listener = AddTaskListener()
        self.list_listener = ListTasksListener()
        self.action_menu_listener = TaskActionMenuListener()
        self.annotate_listener = AnnotateTaskListener()

    def on_event(self, event, extension):
        if not is_tool_installed('task'):
            return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

        keyword = event.get_keyword()
        argument = event.get_argument() or ""

        # --- NEW ROUTING LOGIC ---
        if keyword == extension.preferences['list_kw']:
            # If the argument looks like a UUID, show the action menu.
            if UUID_REGEX.match(argument.strip()):
                return self.action_menu_listener.on_event(event, extension)
            # Otherwise, show the normal task list.
            else:
                return self.list_listener.on_event(event, extension)
        
        elif keyword == extension.preferences['add_kw']:
            return self.add_listener.on_event(event, extension)
            
        elif keyword == extension.preferences['annotate_kw']:
            return self.annotate_listener.on_event(event, extension)


class TaskwarriorExtension(Extension):
    """The main extension class that Ulauncher interacts with."""
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
