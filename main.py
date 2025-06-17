import logging
import subprocess
import json
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction

# It's good practice to set up logging to see what's happening.
# You can view Ulauncher logs by running `ulauncher -v` in a terminal.
logging.basicConfig()
logger = logging.getLogger(__name__)

# A single, simple function to show an error message in Ulauncher.
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

# A function to check if Taskwarrior is installed before we do anything else.
def is_taskwarrior_installed():
    """Checks if the 'task' command-line tool is available."""
    try:
        # Use a simple, non-altering command to check.
        subprocess.run(['task', '--version'], capture_output=True, check=True)
        return True
    except FileNotFoundError:
        # This error means the 'task' command wasn't found at all.
        logger.error("The 'task' command was not found.")
        return False
    except subprocess.CalledProcessError as e:
        # This means 'task' exists but returned an error. Still a problem.
        logger.error("Error when calling 'task --version': %s", e)
        return False

class AddTaskListener:
    """Handles the 'add task' keyword query."""
    def on_event(self, event, extension):
        # The text the user typed after the keyword 't'
        task_description = event.get_argument()

        if not task_description:
            return show_error_item("Please enter a description for the new task.")

        # This command will be executed in the shell when the user presses Enter.
        # 'rc.confirmation=off' prevents Taskwarrior from asking "Are you sure?".
        command = f"task rc.confirmation=off add {task_description}"

        # We create a single result item. When the user selects it,
        # the RunScriptAction will execute our command.
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
        # The user can type after 'tl' to filter, e.g., 'tl +projectX'
        filter_args = event.get_argument() or "pending"

        try:
            # 'task export' gives us clean JSON data, which is easy and reliable to work with.
            command = ['task', filter_args, 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)

            if not tasks:
                return show_error_item(f"No tasks found matching: '{filter_args}'")

            items = []
            for task in tasks:
                # For now, selecting a task will just close Ulauncher.
                # We are not adding sub-menus or other actions yet.
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


class TaskwarriorExtension(Extension):
    """The main extension class."""
    def __init__(self):
        super().__init__()
        
        # Before we set up our listeners, we do a single check.
        # If Taskwarrior isn't installed, the extension won't do anything.
        if not is_taskwarrior_installed():
            logger.error("Taskwarrior is not installed or not in PATH. Extension will not be functional.")
            # We can't show an item here because no keyword has been typed yet.
            # The check will run again inside each listener.
            return

        # Map our keywords to our listener classes.
        self.subscribe(KeywordQueryEvent, self.on_keyword_query)
        self.add_keyword_listener = AddTaskListener()
        self.list_keyword_listener = ListTasksListener()

    def on_keyword_query(self, event, extension):
        # First, a safety check in case the initial one failed.
        if not is_taskwarrior_installed():
            return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

        # Route the event to the correct listener based on the keyword from manifest.json
        keyword = event.get_keyword()
        if keyword == self.preferences['add_kw']:
            return self.add_keyword_listener.on_event(event, extension)
        elif keyword == self.preferences['list_kw']:
            return self.list_keyword_listener.on_event(event, extension)


if __name__ == '__main__':
    TaskwarriorExtension().run()
