## Alembic Migrations

The initial database schema and subsequent database migrations are captured in this folder.
For a fresh install of the LMS backend, there is no need to run migrations and the database can be installed from the SQLModel schema metadata.

To do this run
```bash
python -m app.initial_data
```

Note: that this action is destructive and will remove any existing data in the database. It **SHOULD NOT** be used in production, except for the first time setting up the database.


On subsequent data migrations the following command is run to get alembic migrations:

```bash
alembic upgrade head
```

To do a downgrade, you can either specify how many steps backwards or specify a version.

To downgrade 1 step backwards:
```bash
alembic downgrade -1
```

To downgrade to a specific version, use the history command to identify which version you wish to downgrade to. This prints a list of all the migrations.
```bash
alembic history
```

Then run the desired migration:
```bash
alembic downgrade <hash>
```
