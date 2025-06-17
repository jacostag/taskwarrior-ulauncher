import logging
import subprocess
import json
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction

# Set up logging so we can see what's happening in the Ulauncher logs.
logging.basicConfig()
logger = logging.getLogger(__name__)

# --- Helper Functions (Unchanged) ---

def show_error_item(title, description=""):
    """Creates a Ulauncher item to display an error message."""
    return RenderResultListAction([
        ExtensionResultItem(
            icon='images/icon.png',
            name=title,
            description=description,
            on_enter=HideWindowAction()
        )
    ])

def is_taskwarrior_installed():
    """Checks if the 'task' command-line tool is available."""
    try:
        subprocess.run(['task', '--version'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.error("The 'task' command was not found or failed to run.")
        return False

# --- Individual Action Listeners (Unchanged) ---

class AddTaskListener:
    """Handles the 'add task' keyword query."""
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
    """Handles the 'list tasks' keyword query."""
    def on_event(self, event, extension):
        filter_args = event.get_argument() or "pending"
        try:
            command = ['task', filter_args, 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)

            if not tasks:
                return show_error_item(f"No tasks found matching: '{filter_args}'")

            items = []
            for task in tasks:
                items.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=f"[{task['id']}] {task['description']}",
                        description=f"Project: {task.get('project', 'None')} | Urgency: {task.get('urgency', 0):.2f}",
                        on_enter=HideWindowAction()
                    )
                )
            return RenderResultListAction(items)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error("Error parsing Taskwarrior JSON: %s", e)
            return show_error_item("Error running 'task' command.", str(e))

# --- The Fix is Here: A Proper Event Router ---

class KeywordQueryEventListener:
    """
    This is the main listener object. Ulauncher sends all keyword events here,
    and this class decides which specialized listener to use.
    """
    def __init__(self):
        # Create an instance of each specialized listener.
        self.add_listener = AddTaskListener()
        self.list_listener = ListTasksListener()

    def on_event(self, event, extension):
        """This is the method Ulauncher will call."""
        # First, a safety check.
        if not is_taskwarrior_installed():
            return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

        # Get the keyword the user typed (e.g., 't' or 'tl').
        keyword = event.get_keyword()

        # Route the event to the correct listener object based on the keyword.
        if keyword == extension.preferences['add_kw']:
            return self.add_listener.on_event(event, extension)
        elif keyword == extension.preferences['list_kw']:
            return self.list_listener.on_event(event, extension)

# --- Main Extension Class (Now much simpler) ---

class TaskwarriorExtension(Extension):
    """The main extension class that Ulauncher interacts with."""
    def __init__(self):
        super().__init__()
        # We subscribe an INSTANCE of our new routing class.
        # This fixes the "AttributeError: 'function' object has no attribute 'on_event'"
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
