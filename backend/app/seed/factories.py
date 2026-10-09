from typing import Any

from app.actions import account_action, profile_action


def account_action_factory(**kwargs: object) -> Any:
    # Keep kwargs for compatibility with class_factory injection.
    return account_action


def profile_action_factory(**kwargs: object) -> Any:
    # Keep kwargs for compatibility with class_factory injection.
    return profile_action
