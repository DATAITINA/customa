import textwrap
from pathlib import Path

from app.actions import account_action as aa
from app.seed import runner


def seeders_yml(path: Path) -> str:
    content = """
        seeders:
          admin:
            name: admin
            action:
              class_factory: app.seed.factories.account_action_factory
            records:
              - username: admin2@example.com
                email: admin2@example.com
                password: string
                role: root

          trainer:
            name: trainer
            action:
              class_factory: app.seed.factories.account_action_factory
            records:
              - username: trainer@example.com
                email: trainer@example.com
                password: string
                role: user

          student:
            name: student
            action:
              class_factory: app.seed.factories.account_action_factory
            records:
              - username: student@example.com
                email: student@example.com
                password: string
                role: user
        """
    yml_path = path / "seeders.yml"
    yml_path.write_text(textwrap.dedent(content))
    return str(yml_path)


def test_run_seeders_with_init_db(tmp_path, session):
    initial_accts = aa.get_multi(session)
    assert len(initial_accts) == 1  # init_db superuser

    runner.main(
        argv=[
            "--db-url",
            str(session.bind.url),
            "--yes",
            "--seeders-yml",
            seeders_yml(tmp_path),
            "--init-db",
        ]
    )

    assert len(aa.get_multi(session)) == 3
    assert aa.get_by_email(session, email="admin2@example.com")
    assert aa.get_by_email(session, email="trainer@example.com")
    assert aa.get_by_email(session, email="student@example.com")


def test_run_seeders_with_init_db_and_seed_only(tmp_path, session):
    initial_accts = aa.get_multi(session)
    assert len(initial_accts) == 1  # init_db superuser

    runner.main(
        argv=[
            "--db-url",
            str(session.bind.url),
            "--yes",
            "--seeders-yml",
            seeders_yml(tmp_path),
            "--init-db",
            "--seeders",
            "student",
            "trainer",
        ]
    )

    assert len(aa.get_multi(session)) == 2
    assert not aa.get_by_email(session, email="admin2@example.com")
    assert aa.get_by_email(session, email="trainer@example.com")
    assert aa.get_by_email(session, email="student@example.com")


def test_run_seeders_with_seed_only(tmp_path, session, caplog):
    initial_accts = aa.get_multi(session)
    assert len(initial_accts) == 1  # init_db superuser

    runner.main(
        argv=[
            "--db-url",
            str(session.bind.url),
            "--yes",
            "--seeders-yml",
            seeders_yml(tmp_path),
            "--seeders",
            "admin",
        ]
    )

    assert "Database initialization requested" not in caplog.text

    assert len(aa.get_multi(session)) == 2
    assert aa.get_by_email(session, email="admin2@example.com")
    assert not aa.get_by_email(session, email="trainer@example.com")
    assert not aa.get_by_email(session, email="student@example.com")


def test_run_seeders_with_no_sysargs(tmp_path, session, caplog):
    initial_accts = aa.get_multi(session)
    assert len(initial_accts) == 1  # init_db superuser

    runner.main(
        argv=[
            "--db-url",
            str(session.bind.url),
            "--yes",
            "--seeders-yml",
            seeders_yml(tmp_path),
        ]
    )

    assert "Database initialization requested" not in caplog.text

    assert len(aa.get_multi(session)) == 4
    assert aa.get_by_email(session, email="admin2@example.com")
    assert aa.get_by_email(session, email="trainer@example.com")
    assert aa.get_by_email(session, email="student@example.com")
