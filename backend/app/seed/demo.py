"""Idempotent seed for the stage demo: Iya Bisi's stand and its vendor login.

Safe to run on every start: anything that already exists is left alone.
"""

from sqlmodel import Session

from app import models
from app.actions import account_action, character_action, user_action, workspace_action
from app.core.config import settings
from app.services.stands import create_stand, set_stand_setting

DEMO_SLUG = "iya-bisi-demo"

BISI = models.CharacterCreate(
    name="Bisi Pepper",
    body=models.CharacterBody.pepper,
    color="pepper",
    accessory="headwrap",
    greeting="Ah, welcome o! Yam and fish dey hot. Sit down make I serve you.",
    personality=(
        "Bisi Pepper is the cheerful pepper mascot of Iya Bisi's Yam & Fish stand. "
        "Warm, quick, a little cheeky, proud of the food. Speaks friendly English "
        "with light Nigerian Pidgin."
    ),
    menu=[
        {"item": "Boiled yam and fish stew", "price": 1500},
        {"item": "Fried yam and pepper sauce", "price": 1200},
        {"item": "Yam and egg sauce", "price": 1300},
        {"item": "Extra fish", "price": 800},
        {"item": "Bottled water", "price": 300},
    ],
)


def seed_demo_stand(session: Session) -> None:
    vendor = account_action.get_by_email(session, email=settings.DEMO_VENDOR_EMAIL)
    if vendor is None:
        vendor = account_action.create(
            session,
            data=models.AccountCreate(
                username="iyabisi",
                email=settings.DEMO_VENDOR_EMAIL,
                phone=None,  # phone is unique, so leave it empty rather than ""
                password=settings.DEMO_VENDOR_PASSWORD,
                status=models.AccountStatus.active,
                role=models.AccountRole.user,
                profile=models.ProfileCreate(first_name="Iya", last_name="Bisi"),
            ),
        )

    workspace = workspace_action.get_by_all(session, slug=DEMO_SLUG)
    if workspace is None:
        workspace, _ = create_stand(
            session,
            owner=vendor,
            name="Iya Bisi's Yam & Fish (Demo)",
            description="Fictional demo stand for the Customa stage demo",
            character=BISI,
            slug=DEMO_SLUG,
        )
    elif character_action.get_for_stand(session, workspace_id=workspace.id) is None:
        character_action.create(session, data=BISI, update={"workspace_id": workspace.id})

    # Seeding runs outside a request, so the workspace hook that adds the owner
    # as a member does not fire. Add the membership directly (idempotent).
    user_action.create_membership(
        session, account_id=vendor.id, workspace_id=workspace.id, owner_id=vendor.id
    )
    if vendor.current_workspace_id is None:
        vendor.current_workspace_id = workspace.id
        session.add(vendor)

    # The stage demo counts a new plate every 30 seconds instead of 6 hours.
    set_stand_setting(session, workspace, "PLATE_WINDOW_SECONDS", 30)
    # The three return-visit features are on so they can be shown. The bank details are
    # deliberately not a real account, so nobody watching a demo can send money to it.
    for key, value in (
        ("PLATE_AJO_ENABLED", True),
        ("AJO_BANK_NAME", "Demo Bank"),
        ("AJO_ACCOUNT_NUMBER", "0000000000"),
        ("AJO_ACCOUNT_NAME", "DEMO STAND - DO NOT PAY"),
        ("POT_ALERT_ENABLED", True),
        ("LUNCH_CREW_ENABLED", True),
    ):
        set_stand_setting(session, workspace, key, value)
    session.commit()
