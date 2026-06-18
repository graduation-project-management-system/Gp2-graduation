"""
Application Use Cases — orchestrate domain objects to fulfill supervisor features.
Each use case has one public method and depends only on domain interfaces.
"""
from typing import List, Optional
import datetime

from ..domain.entities import (
    AvailabilitySlotEntity, MeetingEntity, GradingReportEntity,
    SupervisorRequestEntity, TeamFileEntity, NotificationEntity,
)
from ..domain.value_objects import (
    MeetingType, SlotMode, GradingPhase, WeightedGrade,
)
from ..domain.services import SlotFinderService, FairnessCheckerService
from ..domain.events import (
    MeetingScheduledEvent, RequestApprovedEvent,
    RequestForwardedEvent, RequestExhaustedEvent, GradeSubmittedEvent,
)
from ..domain.repositories import (
    ITeamRepository, IAvailabilitySlotRepository, IMeetingRepository,
    IGradingReportRepository, ISupervisorRequestRepository,
    ITeamFileRepository, INotificationRepository,
)


# ── Availability Slots ────────────────────────────────────────────────────────

class ManageAvailabilityUseCase:
    """Add / remove / list availability slots for a supervisor."""

    def __init__(self, slot_repo: IAvailabilitySlotRepository):
        self._slot_repo = slot_repo

    def list_slots(self, supervisor_id: int) -> List[AvailabilitySlotEntity]:
        return self._slot_repo.get_by_supervisor(supervisor_id)

    def add_slot(
        self,
        supervisor_id: int,
        date:          datetime.date,
        start_time:    datetime.time,
        end_time:      datetime.time,
        mode:          SlotMode,
    ) -> AvailabilitySlotEntity:
        return self._slot_repo.create(supervisor_id, date, start_time, end_time, mode)

    def remove_slot(self, supervisor_id: int, slot_id: int) -> None:
        slot = self._slot_repo.get_by_id(slot_id, supervisor_id)
        if slot is None:
            raise ValueError('Slot not found or does not belong to you.')
        self._slot_repo.delete(slot_id, supervisor_id)


# ── Schedule Meeting ──────────────────────────────────────────────────────────

class ScheduleMeetingUseCase:
    """
    Auto-select the earliest available slot and book a meeting.
    Enforces: team assignment, exam-date conflict, fairness check.
    Raises MeetingScheduledEvent to trigger notifications.
    """

    def __init__(
        self,
        team_repo:    ITeamRepository,
        meeting_repo: IMeetingRepository,
        slot_repo:    IAvailabilitySlotRepository,
        notif_repo:   INotificationRepository,
    ):
        self._team_repo    = team_repo
        self._meeting_repo = meeting_repo
        self._slot_repo    = slot_repo
        self._notif_repo   = notif_repo
        self._slot_finder  = SlotFinderService(slot_repo, meeting_repo)
        self._fairness     = FairnessCheckerService(team_repo, meeting_repo)

    def execute(
        self,
        supervisor_id:   int,
        supervisor_name: str,
        team_id:         int,
        meeting_type:    MeetingType,
        topic:           str,
    ) -> MeetingEntity:

        # 1 — verify team exists and is assigned to this supervisor
        team = self._team_repo.get_by_id(team_id)
        if team is None:
            raise ValueError('Team not found.')
        if team.assigned_supervisor_id != supervisor_id:
            raise PermissionError('This team is not assigned to you.')

        # 2 — fetch exam dates (blocked dates)
        exam_dates = set(self._team_repo.get_exam_dates(team_id))

        # 3 — fairness check
        ok, err = self._fairness.check(supervisor_id, team_id)
        if not ok:
            raise ValueError(err)

        # 4 — find best slot, already skipping exam days
        result = self._slot_finder.find_best_slot(supervisor_id, meeting_type, exam_dates)
        if result is None:
            raise ValueError('No available slot found. All slots may be on exam days or fully booked.')

        date, time = result

        # 5 — persist meeting
        meeting = self._meeting_repo.create(
            supervisor_id, team_id, date, time, meeting_type, topic
        )

        # 6 — raise event → send notifications
        event = MeetingScheduledEvent(
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            team_id=team_id,
            team_name=team.name,
            member_ids=team.member_ids,
            date=date,
            time=time,
            meeting_type=meeting_type.value,
            topic=topic,
        )
        self._on_meeting_scheduled(event)
        return meeting

    def _on_meeting_scheduled(self, event: MeetingScheduledEvent):
        msg = (
            f'Dr. {event.supervisor_name} scheduled a {event.meeting_type} '
            f'meeting on {event.date} at {event.time.strftime("%H:%M")}. '
            f'Topic: {event.topic or "—"}'
        )
        for member_id in event.member_ids:
            self._notif_repo.create(
                recipient_id=member_id,
                title='Meeting scheduled',
                message=msg,
                notif_type='meeting_scheduled',
                team_name=event.team_name,
            )
        self._notif_repo.create(
            recipient_id=event.supervisor_id,
            title='Meeting booked',
            message=(
                f'Meeting with {event.team_name} booked on '
                f'{event.date} at {event.time.strftime("%H:%M")}.'
            ),
            notif_type='meeting_booked',
            team_name=event.team_name,
        )


# ── List Meetings ─────────────────────────────────────────────────────────────

class GetMeetingsUseCase:
    """Retrieve all meetings for a supervisor."""

    def __init__(self, meeting_repo: IMeetingRepository):
        self._meeting_repo = meeting_repo

    def execute(self, supervisor_id: int) -> List[MeetingEntity]:
        return self._meeting_repo.get_by_supervisor(supervisor_id)


# ── Supervision Requests ──────────────────────────────────────────────────────

class DecideSupervisionRequestUseCase:
    """
    Approve or reject a pending supervision request.
    On rejection: forward to the next preference; if exhausted, mark as fully rejected.
    On approval: assign supervisor to the team.
    """

    def __init__(
        self,
        request_repo: ISupervisorRequestRepository,
        team_repo:    ITeamRepository,
        notif_repo:   INotificationRepository,
    ):
        self._request_repo = request_repo
        self._team_repo    = team_repo
        self._notif_repo   = notif_repo

    def list_pending(self, supervisor_id: int) -> List[SupervisorRequestEntity]:
        return self._request_repo.get_pending_for_supervisor(supervisor_id)

    def decide(
        self,
        supervisor_id:   int,
        supervisor_name: str,
        request_id:      int,
        decision:        str,
    ) -> SupervisorRequestEntity:

        if decision not in ('approve', 'reject'):
            raise ValueError("decision must be 'approve' or 'reject'.")

        req = self._request_repo.get_by_id(request_id)
        if req is None:
            raise ValueError('Request not found.')
        if req.target_supervisor_id != supervisor_id:
            raise PermissionError('This request is not targeted at you.')
        if req.status.value != 'pending':
            raise ValueError('This request is already decided.')

        if decision == 'approve':
            return self._approve(req, supervisor_id, supervisor_name)
        else:
            return self._reject(req, supervisor_id)

    def _approve(
        self,
        req:             SupervisorRequestEntity,
        supervisor_id:   int,
        supervisor_name: str,
    ) -> SupervisorRequestEntity:
        updated = self._request_repo.approve(req.id, supervisor_id)
        self._team_repo.assign_supervisor(req.team_id, supervisor_id)

        team = self._team_repo.get_by_id(req.team_id)
        event = RequestApprovedEvent(
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            team_id=req.team_id,
            team_name=req.team_name,
            member_ids=team.member_ids if team else [],
        )
        for member_id in event.member_ids:
            self._notif_repo.create(
                recipient_id=member_id,
                title='Supervisor assigned',
                message=f'Dr. {supervisor_name} accepted to supervise {req.team_name}.',
                notif_type='supervisor_assigned',
                team_name=req.team_name,
            )
        return updated

    def _reject(
        self,
        req:           SupervisorRequestEntity,
        supervisor_id: int,
    ) -> SupervisorRequestEntity:
        next_sup_id = req.next_supervisor_id()

        if next_sup_id is not None:
            # Forward to next preference
            updated = self._request_repo.forward_or_reject(
                req.id, next_sup_id, req.current_index + 1
            )
            event = RequestForwardedEvent(
                next_supervisor_id=next_sup_id,
                team_name=req.team_name,
                project_idea=req.project_idea,
            )
            self._notif_repo.create(
                recipient_id=event.next_supervisor_id,
                title='New team request',
                message=f'{req.team_name} requests you as supervisor (forwarded).',
                notif_type='supervisor_request',
                team_name=req.team_name,
            )
        else:
            # All preferences exhausted
            updated = self._request_repo.forward_or_reject(req.id, None, req.current_index + 1)
            event = RequestExhaustedEvent(
                leader_id=req.leader_id,
                team_name=req.team_name,
            )
            self._notif_repo.create(
                recipient_id=event.leader_id,
                title='Supervisor request rejected',
                message='All selected supervisors declined. Please submit a new request.',
                notif_type='request_rejected',
                team_name=req.team_name,
            )

        return updated


# ── Grading Reports ───────────────────────────────────────────────────────────

class SubmitGradingReportUseCase:
    """
    Submit a grading report for a team.
    Enforces: team assignment, unique_together (team+phase).
    Sends notifications to all team members.
    """

    def __init__(
        self,
        grading_repo: IGradingReportRepository,
        team_repo:    ITeamRepository,
        notif_repo:   INotificationRepository,
    ):
        self._grading_repo = grading_repo
        self._team_repo    = team_repo
        self._notif_repo   = notif_repo

    def list_reports(self, supervisor_id: int) -> List[GradingReportEntity]:
        return self._grading_repo.get_by_supervisor(supervisor_id)

    def submit(
        self,
        supervisor_id:        int,
        supervisor_name:      str,
        team_id:              int,
        phase:                GradingPhase,
        chief_grade:          float,
        examiner_one_grade:   Optional[float],
        examiner_two_grade:   Optional[float],
        feedback:             str,
    ) -> GradingReportEntity:

        team = self._team_repo.get_by_id(team_id)
        if team is None:
            raise ValueError('Team not found.')
        if team.assigned_supervisor_id != supervisor_id:
            raise PermissionError('This team is not assigned to you.')

        weighted = WeightedGrade(
            chief_grade=chief_grade,
            examiner_one_grade=examiner_one_grade,
            examiner_two_grade=examiner_two_grade,
        )

        entity = GradingReportEntity(
            id=None,
            supervisor_id=supervisor_id,
            team_id=team_id,
            team_name=team.name,
            phase=phase,
            grade=weighted,
            feedback=feedback,
        )
        report = self._grading_repo.create(entity)

        event = GradeSubmittedEvent(
            supervisor_name=supervisor_name,
            team_id=team_id,
            team_name=team.name,
            member_ids=team.member_ids,
            final_grade=report.final_grade,
        )
        for member_id in event.member_ids:
            self._notif_repo.create(
                recipient_id=member_id,
                title='Grade submitted',
                message=(
                    f'Dr. {supervisor_name} submitted your {phase.value} grade. '
                    + (f'Final: {event.final_grade:.1f}/100' if event.final_grade is not None else 'Awaiting examiner grades.')
                ),
                notif_type='grade_published',
                team_name=team.name,
            )

        return report


# ── Files ─────────────────────────────────────────────────────────────────────

class ManageFilesUseCase:
    """View and delete files uploaded by teams under this supervisor."""

    def __init__(self, file_repo: ITeamFileRepository):
        self._file_repo = file_repo

    def list_files(self, supervisor_id: int) -> List[TeamFileEntity]:
        return self._file_repo.get_for_supervisor_teams(supervisor_id)

    def delete_file(self, supervisor_id: int, file_id: int) -> None:
        file = self._file_repo.get_by_id(file_id)
        if file is None:
            raise ValueError('File not found.')
        self._file_repo.delete(file_id)


# ── Notifications ─────────────────────────────────────────────────────────────

class GetNotificationsUseCase:
    """Retrieve, read, and delete notifications for any authenticated user."""

    def __init__(self, notif_repo: INotificationRepository):
        self._notif_repo = notif_repo

    def list(self, user_id: int) -> List[NotificationEntity]:
        return self._notif_repo.get_for_user(user_id)

    def mark_read(self, user_id: int, notif_id: int) -> None:
        found = self._notif_repo.mark_as_read(notif_id, user_id)
        if not found:
            raise ValueError('Notification not found.')

    def delete(self, user_id: int, notif_id: int) -> None:
        found = self._notif_repo.delete(notif_id, user_id)
        if not found:
            raise ValueError('Notification not found.')
