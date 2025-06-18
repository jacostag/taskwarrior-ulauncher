import logging
import subprocess
import json
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

# We are setting logging to DEBUG to get maximum information.
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def show_error_item(title, description=""):
    """A helper function to safely display an error message in Ulauncher."""
    logger.error("Displaying error to user: %s - %s", title, description)
    return RenderResultListAction([
        ExtensionResultItem(icon='images/icon.png', name=title, description=description, on_enter=HideWindowAction())
    ])

class DiagnosticListTasksListener:
    """This listener will only try to list tasks and has enhanced error handling."""
    def on_event(self, event, extension):
        # We are hard-coding the command to remove all other variables.
        command = ['task', '+READY', 'rc.verbose=nothing', 'export']
        
        try:
            logger.info("Attempting to run command: %s", " ".join(command))
            
            # This is the critical part: we run the command with a 5-second timeout.
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=True, 
                timeout=5
            )
            
            logger.info("Command finished successfully. Parsing JSON.")
            tasks = json.loads(result.stdout)

            if not tasks:
                return show_error_item("Command successful, but no tasks found.")

            items = []
            for task in tasks:
                # We are keeping the display logic as simple as possible.
                items.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=task.get('description', 'Task has no description'),
                        on_enter=HideWindowAction()
                    )
                )
            
            logger.info("Successfully built %d task items.", len(items))
            return RenderResultListAction(items)

        except subprocess.TimeoutExpired:
            logger.error("The 'task' command timed out after 5 seconds.")
            return show_error_item("Error: Command Timed Out", "The 'task' command took too long to respond.")
        
        except subprocess.CalledProcessError as e:
            logger.error("The 'task' command failed with an error: %s", e)
            logger.error("Stderr: %s", e.stderr)
            return show_error_item("Error: Task Command Failed", e.stderr)

        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from Taskwarrior: %s", e)
            return show_error_item("Error: Invalid Data", "Taskwarrior returned data that was not valid JSON.")

        except Exception as e:
            # A catch-all for any other unexpected errors.
            logger.error("An unexpected critical error occurred: %s", e, exc_info=True)
            return show_error_item("A Critical Error Occurred", str(e))

class TaskwarriorExtension(Extension):
    """The main extension class."""
    def __init__(self):
        super().__init__()
        # We only subscribe to the 'tl' keyword for this test.
        self.subscribe(KeywordQueryEvent, DiagnosticListTasksListener())

if __name__ == '__main__':
    TaskwarriorExtension().run()
