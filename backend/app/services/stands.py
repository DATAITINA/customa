"""Stand helpers: tiered settings and creating a vendor's stand."""

from datetime import datetime

from msflib.utils.utils import slugify
from msflib.workspace_config.models import ConfigScopeType
from msflib.workspace_config.service import ScopedConfigService
from msflib.workspaces.models import WorkspaceCreate
from sqlmodel import Session

from ..actions import character_action, tenant_action, workspace_action
from ..core.config import CustomaSettings, settings
from ..models import Account, Character, CharacterCreate, Workspace

config_service = ScopedConfigService()


def resolve_stand_settings(session: Session, workspace: Workspace) -> CustomaSettings:
    """Customa settings for one stand: code defaults, then that stand's overrides.

    MSFLib's tiered config merges default -> tenant -> workspace, so a single
    stored workspace value (like a shorter plate window) wins.
    """
    return config_service.resolve_module_settings(
        session,
        settings.scope("CUSTOMA").unwrap(),
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
    )


def set_stand_setting(session: Session, workspace: Workspace, key: str, value) -> None:
    config_service.set_value(
        session, ConfigScopeType.workspace, "CUSTOMA", key, value, workspace_id=workspace.id
    )


def create_stand(
    session: Session,
    *,
    owner: Account,
    name: str,
    description: str,
    character: CharacterCreate,
    slug: str | None = None,
) -> tuple[Workspace, Character]:
    """A stand is an MSFLib workspace owned by the vendor, plus its character.

    The workspaces module's event hook makes the owner a member, which is what
    lets the vendor through the workspace membership checks on the dashboard.
    """
    tenant = tenant_action.ensure_default_tenant(session, settings=settings.scope("TENANCY"))
    workspace = workspace_action.create_with_owner(
        session,
        data=WorkspaceCreate(
            name=name,
            slug=slug or slugify(name),
            description=description,
            owner_id=owner.id,
            status="open",
        ),
        owner=owner,
        tenant=tenant,
    )
    char = character_action.create(session, data=character, update={"workspace_id": workspace.id})
    return workspace, char


def last_plates(stand_settings: CustomaSettings) -> dict | None:
    """The stand's live "last plates" announcement, or None if there is none."""
    until = stand_settings.LAST_PLATES_UNTIL
    if not until or stand_settings.LAST_PLATES_LEFT <= 0:
        return None
    if datetime.fromisoformat(until) <= datetime.utcnow():
        return None
    return {"left": stand_settings.LAST_PLATES_LEFT, "until": until}
