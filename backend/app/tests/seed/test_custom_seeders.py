from types import SimpleNamespace

from app.seed.seeders.user import UserSeeder
from app.seed.seeders.workspace import WorkspaceSeeder


def test_workspace_seeder_seeds_all_records_with_admin_owner(monkeypatch):
    config = SimpleNamespace(name="workspaces", records=[{"name": "w1"}, {"name": "w2"}])
    seeder = WorkspaceSeeder(config)

    admin = SimpleNamespace(id=1, role="admin")
    member = SimpleNamespace(id=2, role="user")
    seeds = {"accounts": [member, admin]}

    monkeypatch.setattr("app.seed.seeders.workspace.get_dependency_value", lambda _c, _s: {"x": 1})

    random_calls = []
    create_calls = []

    def fake_random(**kwargs):
        random_calls.append(kwargs)
        return {"randomized": kwargs}

    def fake_create(session, owner, data, update):
        create_calls.append({"session": session, "owner": owner, "data": data, "update": update})
        return {"id": len(create_calls)}

    monkeypatch.setattr("app.seed.seeders.workspace.wa.random", fake_random)
    monkeypatch.setattr("app.seed.seeders.workspace.wa.create", fake_create)

    session = object()
    seeder.seed(session, seeds)

    assert random_calls == [{"name": "w1"}, {"name": "w2"}]
    assert len(create_calls) == 2
    assert all(call["owner"] is admin for call in create_calls)
    assert seeds["workspaces"] == [{"id": 1}, {"id": 2}]


def test_user_seeder_seeds_all_accounts_when_only_one_record(monkeypatch):
    config = SimpleNamespace(name="users", records=[{"type": "learner", "nickname": "seeded"}])
    seeder = UserSeeder(config)

    seeds = {
        "accounts": [
            SimpleNamespace(id=10),
            SimpleNamespace(id=11),
            SimpleNamespace(id=12),
        ]
    }

    monkeypatch.setattr(
        "app.seed.seeders.user.get_dependency_value", lambda _c, _s: {"active": True}
    )

    create_random_calls = []

    def fake_create_random(_session, account_id, **kwargs):
        create_random_calls.append((account_id, kwargs))
        return SimpleNamespace(id=account_id)

    monkeypatch.setattr("app.seed.seeders.user.ua.create_random", fake_create_random)

    session = object()
    seeder.seed(session, seeds)

    assert [acct_id for acct_id, _ in create_random_calls] == [10, 11, 12]

    for _, payload in create_random_calls:
        assert payload["nickname"] == "seeded"
        assert payload["active"] is True

    assert len(seeds["users"]) == 3
