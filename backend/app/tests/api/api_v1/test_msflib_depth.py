"""MSFLib ai-api (the vendor's "Ask about your stand" agent) and drivelink (stand photos as
files in the vendor's drive), through the real MSFLib routers and real login."""

import base64
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from msflib.utils.tests.account import authentication_token_from_email
from sqlmodel import Session, select

from app.actions import account_action, customer_action, user_action, visit_action
from app.api.api_v1.endpoints import assistant
from app.core.config import settings
from app.models import CharacterCreate, CustomerCreate, StandPhotoFile, VisitCreate
from app.services import stand_assistant
from app.services.stands import create_stand

SLUG = "depth-stand"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
PUBLIC = f"{settings.API_V1_STR}/public/{SLUG}"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Depth", description="Test stand",
        character=CharacterCreate(name="Depth Pot", body="pot", color="palm", accessory="chef",
                                  menu=[{"item": "Jollof rice", "price": 2000}]), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def plates(session: Session, stand, names: list[tuple[str | None, bool, int]]) -> None:
    for name, consent, n in names:
        c = customer_action.create_for_stand(session, workspace_id=stand.id, data=CustomerCreate(first_name=name, consent=consent, source="qr"))
        for i in range(n):
            visit_action.create(session, data=VisitCreate(), update={"workspace_id": stand.id, "customer_id": c.id, "plate_number": i + 1})


SEEN: list[Any] = []


class ScriptedModel(BaseChatModel):
    """A stand-in LLM: first asks for the stand summary tool, then answers from its result."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        SEEN.append(list(messages))
        tool_results = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_results:
            msg = AIMessage(content="", tool_calls=[{"name": "get_stand_summary", "args": {"days": 7}, "id": "call-1"}])
        else:
            msg = AIMessage(content=f"Summary: {tool_results[-1].content}")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def test_stand_tools_read_only_this_stand(session, stand):
    plates(session, stand, [("Ada", True, 3), ("Secret", False, 2)])
    summary = stand_assistant.stand_summary(session, stand.id, days=7)
    assert summary["plates_counted"] == 5 and summary["customers"] == 2 and summary["new_customers"] == 2
    regulars = stand_assistant.top_regulars(session, stand.id)["regulars"]
    assert regulars[0] == {"name": "Ada", "plates": 3, "last_visit_days_ago": 0}
    assert regulars[1]["name"] == "A regular (no name given)"  # no consent: no name
    assert stand_assistant.menu_and_prices(session, stand.id) == {"menu": [{"item": "Jollof rice", "price_naira": 2000}]}
    assert stand_assistant.stand_summary(session, stand.id + 999)["plates_counted"] == 0


def test_assistant_answers_from_the_stand_numbers(client, session, stand, superuser_account_token_headers, monkeypatch):
    plates(session, stand, [("Ada", True, 2)])
    monkeypatch.setattr(assistant._ai, "get_llm", lambda *a, **k: ScriptedModel())
    monkeypatch.setattr(stand_assistant, "open_session", lambda: Session(session.get_bind()))
    r = client.post(f"{VENDOR}/assistant/ask?protocol=langchain", json={"question": "How did this week go?"},
                    headers=superuser_account_token_headers)
    assert r.status_code == 200, r.text
    answer = r.json()["content"]
    assert '"plates_counted": 2' in answer.replace("'", '"')  # the tool ran, scoped to this stand
    # The system prompt went to the model.
    assert any("business helper" in str(m.content) for m in SEEN[0])


def test_assistant_is_for_stand_staff_only(client, session, stand):
    r = client.post(f"{VENDOR}/assistant/ask", json={"question": "hi"})
    assert r.status_code == 401
    # A vendor of another stand: signed in, but not a member of this one.
    outsider = authentication_token_from_email(
        client=client, email="outsider-vendor@example.com", session=session,
        account_action=account_action, oauth_url=f"{settings.API_V1_STR}/login",
    )
    r = client.post(f"{VENDOR}/assistant/ask", json={"question": "hi"}, headers=outsider)
    assert r.status_code == 403


def test_stand_photo_lives_in_the_vendors_drivelink_drive(client, session, stand, superuser_account_token_headers, monkeypatch, tmp_path):
    from msflib.drivelink.models import DrivelinkNode

    monkeypatch.setattr(settings, "STAND_PHOTOS_IN_DRIVELINK", True)
    monkeypatch.setattr(settings, "STORAGE_METHOD", "file")
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    data_url = "data:image/png;base64," + base64.b64encode(PNG).decode()
    r = client.put(f"{VENDOR}/photo", json={"data_url": data_url}, headers=superuser_account_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["photo"].endswith("?v=d1")
    row = session.exec(select(StandPhotoFile)).one()
    node = session.get(DrivelinkNode, row.node_id)
    folder = session.get(DrivelinkNode, node.parent_id)
    assert folder.name == f"Stand photos · {SLUG}" and node.mime_type == "image/png" and node.workspace_id == stand.id
    got = client.get(f"{PUBLIC}/photo")
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"

    # Replacing keeps one file: the old one leaves the drive and storage.
    r = client.put(f"{VENDOR}/photo", json={"data_url": data_url}, headers=superuser_account_token_headers)
    assert r.json()["photo"].endswith("?v=d2")
    session.expire_all()
    files = session.exec(select(DrivelinkNode).where(DrivelinkNode.parent_id == folder.id)).all()
    assert len(files) == 1

    assert client.delete(f"{VENDOR}/photo", headers=superuser_account_token_headers).status_code == 200
    assert client.get(f"{PUBLIC}/photo").status_code == 404


def test_photo_stays_in_the_database_when_drivelink_is_off(client, session, stand, superuser_account_token_headers):
    data_url = "data:image/png;base64," + base64.b64encode(PNG).decode()
    r = client.put(f"{VENDOR}/photo", json={"data_url": data_url}, headers=superuser_account_token_headers)
    assert r.status_code == 200 and "?v=1" in r.json()["photo"]
    assert client.get(f"{PUBLIC}/photo").content == PNG
    assert session.exec(select(StandPhotoFile)).all() == []
