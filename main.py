
import logging
import subprocess
import json
import shlex
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

# --- Replace the existing ListTasksListener with this one for a quick test ---
class ListTasksListener:
    """
    A temporary, simplified version to test if task LISTING is the problem.
    This version disables the action menu.
    """
    def on_event(self, event, extension):
        user_filter = event.get_argument() or "+READY"
        try:
            # We are using the command that we know works.
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
                    display_text = (description[:47] + '...') if len(description) > 50 else description
                    
                    # For this test, we are going back to a simple HideWindowAction.
                    items.append(
                        ExtensionResultItem(
                            icon='images/icon.png',
                            name=display_text,
                            description="Test: This will just close Ulauncher",
                            on_enter=HideWindowAction()
                        )
                    )
                except KeyError:
                    continue
            
            return RenderResultListAction(items)
        except Exception as e:
            logger.error("An unexpected error occurred in the TEST ListTasksListener: %s", e, exc_info=True)
            return show_error_item("An Unexpected Error Occurred", str(e))

class AnnotateTaskListener:
    """Handles adding an annotation to a task. (Unchanged and still necessary)"""
    def on_event(self, event, extension):
        query = event.get_argument()
        if not query or ' ' not in query:
            return show_error_item("Usage: ta <uuid> <annotation text>")
            
        uuid, annotation_text = query.split(' ', 1)
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

# --- Main Event Router (Simplified) ---

class KeywordQueryEventListener:
    """Routes events to the correct listener."""
    def __init__(self):
        self.add_listener = AddTaskListener()
        self.list_listener = ListTasksListener()
        self.annotate_listener = AnnotateTaskListener()

    def on_event(self, event, extension):
        if not is_tool_installed('task'):
            return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

        keyword = event.get_keyword()
        if keyword == extension.preferences['list_kw']:
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
