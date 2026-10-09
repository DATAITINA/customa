from msflib.seed.base import SeederBase
from msflib.seed.schema import ConfigSchema
from msflib.seed.utils import get_dependency_value
from sqlmodel import Session

from app.actions import user_action as ua


class UserSeeder(SeederBase):
    def __init__(self, config: ConfigSchema):
        self.config = config
        self.records = config.records if config.records else [ua.random().dict()]

    def seed(self, session: Session, seeds):
        accounts = seeds["accounts"]
        users = []
        update = get_dependency_value(self.config, seeds)
        for idx, account in enumerate(accounts):
            # If there are fewer records than accounts, reuse the last record.
            record = self.records[idx] if idx < len(self.records) else self.records[-1]
            user = ua.create_random(session, account_id=account.id, **{**record, **update})
            users.append(user)
        seeds.update({self.config.name: users})
