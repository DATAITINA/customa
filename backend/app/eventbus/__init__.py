"""Customa's listeners on the MSFLib event bus.

Every VisitAction.create emits "visit-create-pre-commit" inside the same
database transaction, so the jara is saved together with the visit or not at all.
Crew plates (Lunch Crew) are skipped here: their jara follows the crew's rotation.
"""

from msflib.eventbus import AppEmitter

from ..actions import jara_action
from ..models import Visit, Workspace
from ..services.lunch_crew import is_crew_plate_in_progress
from ..services.stands import resolve_stand_settings


def register_customa_hooks(emitter: AppEmitter) -> None:
    @emitter.on("visit-create-pre-commit")
    def issue_jara_on_last_plate(visit: Visit, options: dict, logger=None) -> None:
        session = options["session"]
        # A Lunch Crew plate: its jara (if any) is issued by lunch_crew.count_crew_plate to the
        # member whose turn it is, never to the scanner here.
        if is_crew_plate_in_progress(session, visit):
            return
        workspace = session.get(Workspace, visit.workspace_id)
        stand_settings = resolve_stand_settings(session, workspace)
        if visit.plate_number == stand_settings.PLATES_FOR_JARA:
            jara_action.issue(session, visit=visit)
