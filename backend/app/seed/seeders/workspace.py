from typing import Any

from msflib.seed.base import SeederBase
from msflib.seed.schema import ConfigSchema
from msflib.seed.utils import get_dependency_value, matches_filters
from sqlmodel import Session

from app.actions import workspace_action as wa


class WorkspaceSeeder(SeederBase):
    def __init__(self, config: ConfigSchema) -> None:
        self.config = config
        self.records = config.records if config.records else [wa.random().dict()]

    def seed(self, session: Session, seeds: dict[str, Any]) -> None:
        workspaces = []
        update = get_dependency_value(self.config, seeds)
        owner = next(
            (acct for acct in seeds["accounts"] if matches_filters(acct, {"role": "admin"})), None
        )
        for record in self.records:
            ws = wa.create(session, owner=owner, data=wa.random(**record), update=update)
            workspaces.append(ws)
        seeds.update({self.config.name: workspaces})
