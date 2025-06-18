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
    """A helper function to safely display an error message in Ulauncher."""
    logger.error("Displaying error to user: %s - %s", title, description)
    return RenderResultListAction([
        ExtensionResultItem(icon='images/icon.png', name=title, description=description, on_enter=HideWindowAction())
    ])

def is_tool_installed(name):
    """Checks if a command-line tool is available."""
    try:
        subprocess.run([name, '--version'], capture_output=True, check=True, text=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# --- All-in-One Event Listener ---

class KeywordEventListener:
    """A single, monolithic listener to handle all extension logic for maximum stability."""

    # We now hard-code the internal annotation keyword because it's no longer in the manifest.
    INTERNAL_ANNOTATE_KEYWORD = "ta"

    def on_event(self, event, extension):
        """This one method will route all actions."""
        try:
            if not is_tool_installed('task'):
                return show_error_item("Taskwarrior not found.", "Please ensure 'task' is installed and in your PATH.")

            keyword = event.get_keyword()
            argument = event.get_argument() or ""

            # Route 1: Add a task
            if keyword == extension.preferences['add_kw']:
                return self.handle_add_task(argument)

            # Route 2: Handle the internal annotation keyword
            elif keyword == self.INTERNAL_ANNOTATE_KEYWORD:
                return self.handle_annotate_task(argument)

            # Route 3: List tasks OR show the action menu
            elif keyword == extension.preferences['list_kw']:
                if UUID_REGEX.match(argument.strip()):
                    return self.show_action_menu(argument.strip())
                else:
                    return self.handle_list_tasks(argument, extension)
            
            return None

        except Exception as e:
            logger.error("A critical unhandled error occurred: %s", e, exc_info=True)
            return show_error_item("A Critical Error Occurred", str(e))

    def handle_add_task(self, description):
        """Logic to add a new task."""
        if not description:
            return show_error_item("Please enter a description for the new task.")
        command = f"task rc.confirmation=off add {description}"
        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png', name=f"Add task: '{description}'", on_enter=RunScriptAction(command))
        ])

    def handle_annotate_task(self, query):
        """Logic to annotate an existing task."""
        if not query or ' ' not in query:
            return show_error_item("Usage: <select annotate> <annotation text>")
        uuid, annotation_text = query.split(' ', 1)
        safe_annotation = shlex.quote(annotation_text)
        command = f"task {uuid} annotate {safe_annotation}"
        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png', name=f"Add annotation to task {uuid[:8]}...", description=f"Note: '{annotation_text}'", on_enter=RunScriptAction(command))
        ])

    def handle_list_tasks(self, user_filter, extension):
        """Logic to fetch and display the list of tasks."""
        filter_to_use = user_filter or "+READY"
        command = ['task', filter_to_use, 'rc.verbose=nothing', 'export']
        
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        tasks = json.loads(result.stdout)

        if not tasks:
            return show_error_item(f"No tasks found for filter: '{filter_to_use}'")

        items = []
        for task in sorted(tasks, key=lambda t: t.get('urgency', 0), reverse=True):
            if not isinstance(task, dict): continue
            description = task.get('description', 'No description')
            uuid = task.get('uuid')
            if not uuid: continue
            
            display_text = (description[:47] + '...') if len(description) > 50 else description
            
            items.append(
                ExtensionResultItem(
                    icon='images/icon.png',
                    name=display_text,
                    description="Press Enter for actions...",
                    on_enter=SetUserQueryAction(f"{extension.preferences['list_kw']} {uuid}")
                )
            )
        return RenderResultListAction(items)

    def show_action_menu(self, uuid):
        """Logic to generate and show the action menu for a UUID."""
        actions = [
            ExtensionResultItem(icon='images/icon.png', name="Mark as Done", on_enter=RunScriptAction(f"task {uuid} done")),
            ExtensionResultItem(icon='images/icon.png', name="Start Task", on_enter=RunScriptAction(f"task {uuid} start")),
            ExtensionResultItem(icon='images/icon.png', name="Stop Task", on_enter=RunScriptAction(f"task {uuid} stop")),
            ExtensionResultItem(icon='images/icon.png', name="Annotate Task", on_enter=SetUserQueryAction(f"{self.INTERNAL_ANNOTATE_KEYWORD} {uuid} ")),
            ExtensionResultItem(icon='images/icon.png', name="Delete Task", on_enter=RunScriptAction(f"task rc.confirmation=off {uuid} delete")),
        ]
        if is_tool_installed('taskopen'):
            actions.append(ExtensionResultItem(icon='images/icon.png', name="Open Task", on_enter=RunScriptAction(f"taskopen {uuid}")))
        return RenderResultListAction(actions)


class TaskwarriorExtension(Extension):
    """The main extension class."""
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordEventListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
