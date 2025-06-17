import json
import logging
import subprocess
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction

# Set up logging
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def is_taskwarrior_installed():
    """Checks if the 'task' command is available in the system's PATH."""
    try:
        subprocess.run(['task', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def run_task_command(command, show_notification=True):
    """
    Runs a Taskwarrior command and returns a Ulauncher action.
    This function will be the single point of execution for all task commands.
    """
    # Use 'rc.confirmation=off' to prevent prompts for commands like 'delete'
    full_command = f"task rc.confirmation=off {command}"
    logger.info("Running command: %s", full_command)
    
    # We use RunScriptAction to execute the shell command.
    # Upon successful execution, Ulauncher will hide its window.
    return RunScriptAction(full_command, None)

def show_error_item(title, description):
    """Creates a standard error item to display in Ulauncher."""
    return RenderResultListAction([
        ExtensionResultItem(
            icon='images/icon.png',
            name=title,
            description=description,
            on_enter=HideWindowAction()
        )
    ])

# --- Base Event Listener ---

class BaseKeywordEventListener:
    """A base class for keyword event listeners to reduce boilerplate."""
    def on_event(self, event, extension):
        # Central check to ensure Taskwarrior is installed before doing anything.
        if not is_taskwarrior_installed():
            return show_error_item(
                "Taskwarrior Not Found",
                "Please make sure 'task' is installed and in your system's PATH."
            )
        # Delegate the actual logic to a subclass method.
        return self.handle_query(event, extension)

    def handle_query(self, event, extension):
        """This method should be implemented by subclasses."""
        raise NotImplementedError

# --- Keyword-Specific Listeners ---

class AddTaskListener(BaseKeywordEventListener):
    """Handles the 't' keyword to add a new task."""
    def handle_query(self, event, extension):
        query = event.get_argument()
        if not query:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='New Task',
                    description='Enter the task description...'
                )
            ])
        
        return RenderResultListAction([
            ExtensionResultItem(
                icon='images/icon.png',
                name=f"Add Task: '{query}'",
                description='Press Enter to create this task',
                on_enter=run_task_command(f"add {query}")
            )
        ])

class ListTasksListener(BaseKeywordEventListener):
    """Handles the 'tl' keyword to list pending tasks."""
    def handle_query(self, event, extension):
        filter_args = event.get_argument() or "pending"
        
        try:
            # Using the JSON export is much more reliable than parsing table text.
            command = ['task', filter_args, 'export']
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            tasks = json.loads(result.stdout)
            
            if not tasks:
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png', name=f"No tasks found for filter: '{filter_args}'")
                ])
            
            items = []
            for task in sorted(tasks, key=lambda t: t.get('urgency', 0), reverse=True):
                description = task.get('description', 'No description')
                task_id = task.get('id')
                project = task.get('project', 'None')
                tags = ', '.join(task.get('tags', []))

                items.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=f"[{task_id}] {description}",
                        description=f"Project: {project} | Tags: {tags}",
                        # When a task is selected, show the list of actions for it.
                        on_enter=SetUserQueryAction(f"{extension.preferences['task_list_kw']} {task_id} ")
                    )
                )
            return RenderResultListAction(items)

        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("Error listing tasks: %s", e)
            return show_error_item("Error Listing Tasks", str(e))

class TaskActionMenuListener(BaseKeywordEventListener):
    """
    Handles displaying the action menu when a task ID is entered after 'tl'.
    Example: 'tl 1' will trigger this.
    """
    def handle_query(self, event, extension):
        query = event.get_argument()
        parts = query.split(' ', 1)
        task_id = parts[0]
        
        # This listener is only for showing the menu for a single task ID.
        if not task_id.isdigit():
            return None # Fallback to ListTasksListener if the query is not just an ID

        kw = extension.preferences
        actions = [
            ExtensionResultItem(icon='images/icon.png', name=f"Mark Task {task_id} as Done", on_enter=run_task_command(f"{task_id} done")),
            ExtensionResultItem(icon='images/icon.png', name=f"Start/Stop Task {task_id}", on_enter=run_task_command(f"{task_id} start") if 'start' not in query else run_task_command(f"{task_id} stop")),
            ExtensionResultItem(icon='images/icon.png', name=f"Delete Task {task_id}", on_enter=run_task_command(f"{task_id} delete")),
            ExtensionResultItem(icon='images/icon.png', name=f"Annotate Task {task_id}", on_enter=SetUserQueryAction(f"{kw['task_annotate_kw']} {task_id} ")),
            ExtensionResultItem(icon='images/icon.png', name=f"Open Task {task_id}", on_enter=run_task_command(f"open {task_id}")),
        ]
        return RenderResultListAction(actions)

class SimpleTaskActionListener(BaseKeywordEventListener):
    """Handles simple actions like done, delete, start/stop which take a task ID."""
    def __init__(self, command_name, description_template):
        self.command_name = command_name
        self.description_template = description_template

    def handle_
