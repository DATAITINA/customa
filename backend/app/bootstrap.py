from msflib.eventbus import AppEmitter
from msflib.workspaces.eventbus import register_event_hooks

from .actions import account_action, user_action, workspace_action
from .core.config import settings

_hooks_registered = False


def bootstrap_module_hooks(emitter: AppEmitter) -> None:
    global _hooks_registered
    if _hooks_registered:
        return

    if workspace_action.settings.AUTO_REGISTER_EVENT_HOOKS:
        register_event_hooks(
            workspace_action=workspace_action,
            user_action=user_action,
            account_action=account_action,
            emitter=emitter,
            tenancy_settings=settings.scope("TENANCY"),
        )
    _hooks_registered = True
