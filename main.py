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

# --- Helper Functions ---

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

# --- Individual Action Listeners ---

class AddTaskListener:
    """Handles the 'add task' keyword query. (This is working and unchanged)"""
    def on_event(self, event, extension):
        task_description = event.get_argument()
        if not task_description:
            return show_error_item("Please enter a description for the new task.")
        
        # Using uuid here for adding is not standard, 'add' creates the uuid.
        # So we use the description as provided by the user.
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
    Handles the 'list tasks' keyword query.
    (This section is updated based on your new requirements)
    """
    def on_event(self, event, extension):
        # We will list all 'pending' tasks. User can still add filters like 'tl +project'.
        filter_args = event.get_argument() or "pending"
        try:
            # The 'task export' command is the best way to get clean data.
            command = ['task', filter_args, 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)

            if not tasks:
                return show_error_item(f"No tasks found matching: '{filter_args}'")

            items = []
            for task in tasks:
                description = task['description']
                uuid = task['uuid']  # We get the uuid for future use.

                # Requirement: Truncate description to 50 characters.
                display_description = (description[:47] + '...') if len(description) > 50 else description
                
                # Requirement: Only the description should be visible.
                items.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=display_description,
                        # For now, selecting a task does nothing but close the window.
                        # In the future, we will use the 'uuid' to build actions here.
                        on_enter=HideWindowAction()
                    )
                )
            return RenderResultListAction(items)
        
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            # This will catch errors if the 'task' command fails or returns invalid data.
            logger.error("Error processing 'task export' command: %s", e)
            return show_error_item("Error Listing Tasks", "Could not get data from Taskwarrior.")

# --- Main Event Router and Extension Class (Unchanged) ---

class KeywordQueryEventListener:
    """Routes events to the correct listener."""
    def __init__(self):
        self.add_listener = AddTaskListener()
        self.list_listener = ListTasksListener()

    def on_event(self, event, extension):
        if not is_taskwarrior_installed():
            return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

        keyword = event.get_keyword()
        if keyword == extension.preferences['add_kw']:
            return self.add_listener.on_event(event, extension)
        elif keyword == extension.preferences['list_kw']:
            return self.list_listener.on_event(event, extension)

class TaskwarriorExtension(Extension):
    """The main extension class that Ulauncher interacts with."""
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
