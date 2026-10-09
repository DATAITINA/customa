from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from app import models
from app.actions import account_action, tenant_action, user_action, workspace_action
from app.core.config import settings
from app.seed.demo import seed_demo_stand

# make sure all SQL Alchemy models are imported (app.models) before initializing DB
# otherwise, SQL Alchemy might fail to initialize relationships properly
# for more details: https://github.com/tiangolo/full-stack-fastapi-postgresql/issues/28


def init_db(engine: Engine, create_tables: bool = False) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, specify True.
    if create_tables:
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        tenant = tenant_action.ensure_default_tenant(session, settings=settings.scope("TENANCY"))
        account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        if not account:
            data = models.AccountCreate(
                username=settings.FIRST_SUPERUSER,
                email=settings.FIRST_SUPERUSER,
                phone="",
                password=settings.FIRST_SUPERUSER_PASSWORD,
                status=models.AccountStatus.active,
                role=models.AccountRole.admin,
                profile=models.ProfileCreate(first_name="Super", last_name="User"),
            )
            account = account_action.create(session, data=data)

        workspace = workspace_action.ensure_default_workspace(
            session,
            owner_id=account.id,
            tenant=tenant,
            commit=False,
        )
        membership = user_action.get_by_all(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
        )
        if membership is None:
            user_action.create_membership(
                session,
                account_id=account.id,
                workspace_id=workspace.id,
                owner_id=workspace.owner_id,
                commit=False,
            )

        if account.current_workspace_id is None:
            account.current_workspace_id = workspace.id
            session.add(account)

        session.commit()

    with Session(engine) as session:
        seed_demo_stand(session)
