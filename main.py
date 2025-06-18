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
logging.basicConfig(level=logging.DEBUG) # Set level to DEBUG to see all messages
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
    Handles the 'list tasks' keyword query.
    (This version is rewritten to be highly defensive and add verbose logging)
    """
    def on_event(self, event, extension):
        filter_args = event.get_argument() or "pending"
        try:
            command = ['task', filter_args, 'export']
            logger.debug("Running command: %s", " ".join(command))
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            raw_json = result.stdout
            
            logger.debug("Received raw output from Taskwarrior: %s", raw_json)

            if not raw_json.strip():
                return show_error_item(f"No tasks found matching: '{filter_args}'", "Taskwarrior returned empty output.")

            tasks = json.loads(raw_json)

            # Defensive Check: Ensure 'tasks' is a list.
            if not isinstance(tasks, list):
                logger.error("Taskwarrior output was not a JSON list. Type is: %s", type(tasks))
                return show_error_item("Error parsing tasks", "Received unexpected data format from Taskwarrior.")

            if not tasks:
                return show_error_item(f"No tasks found matching: '{filter_args}'")

            items = []
            for task in tasks:
                # Defensive Check: Ensure 'task' is a dictionary.
                if not isinstance(task, dict):
                    logger.warning("Skipping item in task list because it is not a dictionary: %s", task)
                    continue

                try:
                    description = task['description']
                    uuid = task['uuid']  # Get uuid for future use
                    
                    display_text = (description[:47] + '...') if len(description) > 50 else description
                    
                    items.append(
                        ExtensionResultItem(
                            icon='images/icon.png',
                            name=display_text,
                            on_enter=HideWindowAction()
                        )
                    )
                except KeyError as e:
                    logger.error("A task object was missing a required key: %s. Task object: %s", e, task)
                    continue # Skip this malformed task and proceed to the next one
            
            if not items:
                return show_error_item("Finished processing, but no valid tasks found.")
            
            return RenderResultListAction(items)
        
        except subprocess.CalledProcessError as e:
            logger.error("The 'task' command failed with an error: %s", e)
            return show_error_item("Taskwarrior Command Failed", str(e))
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from Taskwarrior: %s", e)
            return show_error_item("Error Reading Task Data", "Taskwarrior returned invalid JSON.")
        except Exception as e:
            logger.error("An unexpected error occurred in ListTasksListener: %s", e, exc_info=True)
            return show_error_item("An Unexpected Error Occurred", str(e))

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
