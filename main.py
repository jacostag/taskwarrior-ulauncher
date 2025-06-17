import subprocess
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction


class TaskwarriorExtension(Extension):

    def __init__(self):
        super(TaskwarriorExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())


class KeywordQueryEventListener:

    def on_event(self, event, extension):
        keyword = event.get_keyword()
        query = event.get_argument() or ""

        if keyword == extension.preferences["task_kw"]:
            return self._handle_add_task(query)
        elif keyword == extension.preferences["task_list_kw"]:
            return self._handle_list_tasks(query)
        # Add other keyword handlers here

    def _handle_add_task(self, query):
        if not query:
            return RenderResultListAction(
                [
                    ExtensionResultItem(
                        icon="images/icon.png",
                        name="Add a task",
                        description="Enter the task description and press Enter",
                        on_enter=HideWindowAction(),
                    )
                ]
            )

        return RenderResultListAction(
            [
                ExtensionResultItem(
                    icon="images/icon.png",
                    name=f"Add task: {query}",
                    description="Press Enter to add this task to Taskwarrior",
                    on_enter=self._get_task_action("add", query),
                )
            ]
        )

    def _handle_list_tasks(self, query):
        tasks = self._get_pending_tasks(query)
        if not tasks:
            return RenderResultListAction(
                [
                    ExtensionResultItem(
                        icon="images/icon.png",
                        name="No pending tasks found",
                        on_enter=HideWindowAction(),
                    )
                ]
            )

        items = [
            ExtensionResultItem(
                icon="images/icon.png",
                name=f"({task['id']}) {task['description']}",
                description=f"Project: {task.get('project', 'None')} | Tags: {', '.join(task.get('tags', []))}",
                on_enter=self._get_task_actions(task["id"]),
            )
            for task in tasks
        ]
        return RenderResultListAction(items)

    def _get_pending_tasks(self, query):
        try:
            result = subprocess.run(
                ["task", query, "export"], capture_output=True, text=True, check=True
            )
            return self._parse_tasks(result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    def _parse_tasks(self, output):
        import json

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []

    def _get_task_action(self, command, *args):
        # This will be handled by ItemEnterEventListener
        pass

    def _get_task_actions(self, task_id):
        # This will be handled by ItemEnterEventListener
        pass


class ItemEnterEventListener:

    def on_event(self, event, extension):
        data = event.get_data()
        if not data:
            return

        action = data.get("action")
        task_id = data.get("task_id")
        args = data.get("args", [])

        if action:
            self._run_task_command(action, task_id, *args)

    def _run_task_command(self, command, task_id=None, *args):
        cmd = ["task"]
        if task_id:
            cmd.append(str(task_id))
        cmd.append(command)
        cmd.extend(args)

        try:
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # Handle error, e.g., show a notification
            pass


if __name__ == "__main__":
    TaskwarriorExtension().run()
