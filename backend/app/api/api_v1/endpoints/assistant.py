"""Ask about your stand: MSFLib ai-api's agent router, mounted for stand members only.

POST /stands/{slug}/assistant/ask {"question": "..."} (with ?protocol=langchain the answer comes
back as {"type": "ai", "content": "..."}). The tools and prompt live in
app/services/stand_assistant.py; the LLM is the same ai-core LLM as the character chat.
"""

from fastapi import APIRouter, Depends
from msflib.ai_api.router import create_agent_router
from msflib.ai_core.deps import get_ai_dependencies

from app.api import deps
from app.core.config import settings
from app.models import Workspace
from app.services import stand_assistant

_ai = get_ai_dependencies(settings)


def member_stand(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
) -> Workspace:
    """The stand in the path, only for its own staff: ai-api scopes every tool call to it."""
    return workspace


_agent_router = create_agent_router(
    settings=settings,
    get_session=deps.get_session,
    get_current_account=deps.get_current_active_account,
    get_current_workspace=member_stand,
    get_tool_registries=stand_assistant.tool_registries,
    system_prompt=stand_assistant.SYSTEM_PROMPT,
    model_name_or_factory=lambda: _ai.get_llm(),
    prefix="",
    tags=["assistant"],
)

# Every assistant route (ask, ask/stream, status) needs a signed-in member of this stand,
# checked before ai-api runs: ai-api's own scope dependency accepts anonymous callers.
router = APIRouter(prefix="/stands/{workspace_slug}/assistant", dependencies=[Depends(member_stand)])
router.include_router(_agent_router)
