"""
Infrastructure Layer — Django ORM implementations of domain repository interfaces.
These are the only files that import Django models.
"""
import datetime
from typing import List, Optional, Tuple

from django.utils import timezone

from apps.meetings.models import AvailabilitySlot, Meeting
from apps.teams.models import Team, ExamDate
from apps.grading.models import GradingReport
from apps.requests.models import SupervisorRequest
from apps.files.models import TeamFile
from apps.notifications.models import Notification

from ..domain.entities import (
    AvailabilitySlotEntity, MeetingEntity, TeamEntity,
    GradingReportEntity, SupervisorRequestEntity,
    TeamFileEntity, NotificationEntity,
)
from ..domain.value_objects import (
    MeetingType, SlotMode, TeamStatus,
    RequestStatus, GradingPhase, WeightedGrade,
)
from ..domain.repositories import (
    ITeamRepository, IAvailabilitySlotRepository, IMeetingRepository,
    IGradingReportRepository, ISupervisorRequestRepository,
    ITeamFileRepository, INotificationRepository,
)


# ── Team ──────────────────────────────────────────────────────────────────────

class DjangoTeamRepository(ITeamRepository):

    def get_by_id(self, team_id: int) -> Optional[TeamEntity]:
        try:
            t = Team.objects.prefetch_related('members').get(pk=team_id)
            return self._to_entity(t)
        except Team.DoesNotExist:
            return None

    def get_teams_for_supervisor(self, supervisor_id: int) -> List[TeamEntity]:
        teams = (
            Team.objects
            .filter(assigned_supervisor_id=supervisor_id)
            .prefetch_related('members')
        )
        return [self._to_entity(t) for t in teams]

    def get_exam_dates(self, team_id: int) -> List[datetime.date]:
        return list(
            ExamDate.objects.filter(team_id=team_id).values_list('date', flat=True)
        )

    def assign_supervisor(self, team_id: int, supervisor_id: int) -> None:
        Team.objects.filter(pk=team_id).update(
            assigned_supervisor_id=supervisor_id,
            status='active',
        )

    @staticmethod
    def _to_entity(t: Team) -> TeamEntity:
        return TeamEntity(
            id=t.pk,
            name=t.name,
            status=TeamStatus(t.status),
            leader_id=t.leader_id,
            member_ids=list(t.members.values_list('id', flat=True)),
            assigned_supervisor_id=t.assigned_supervisor_id,
        )


# ── Availability Slots ────────────────────────────────────────────────────────

class DjangoAvailabilitySlotRepository(IAvailabilitySlotRepository):

    def get_by_supervisor(self, supervisor_id: int) -> List[AvailabilitySlotEntity]:
        slots = (
            AvailabilitySlot.objects
            .filter(supervisor_id=supervisor_id)
            .order_by('date', 'start_time')
        )
        return [self._to_entity(s) for s in slots]

    def get_by_id(self, slot_id: int, supervisor_id: int) -> Optional[AvailabilitySlotEntity]:
        try:
            s = AvailabilitySlot.objects.get(pk=slot_id, supervisor_id=supervisor_id)
            return self._to_entity(s)
        except AvailabilitySlot.DoesNotExist:
            return None

    def create(
        self,
        supervisor_id: int,
        date:          datetime.date,
        start_time:    datetime.time,
        end_time:      datetime.time,
        mode:          SlotMode,
    ) -> AvailabilitySlotEntity:
        s = AvailabilitySlot.objects.create(
            supervisor_id=supervisor_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            mode=mode.value,
        )
        return self._to_entity(s)

    def delete(self, slot_id: int, supervisor_id: int) -> bool:
        deleted, _ = AvailabilitySlot.objects.filter(
            pk=slot_id, supervisor_id=supervisor_id
        ).delete()
        return deleted > 0

    @staticmethod
    def _to_entity(s: AvailabilitySlot) -> AvailabilitySlotEntity:
        return AvailabilitySlotEntity(
            id=s.pk,
            supervisor_id=s.supervisor_id,
            date=s.date,
            start_time=s.start_time,
            end_time=s.end_time,
            mode=SlotMode(s.mode),
        )


# ── Meetings ──────────────────────────────────────────────────────────────────

class DjangoMeetingRepository(IMeetingRepository):

    def get_booked_slots(
        self, supervisor_id: int
    ) -> List[Tuple[datetime.date, datetime.time]]:
        return list(
            Meeting.objects
            .filter(supervisor_id=supervisor_id)
            .values_list('date', 'time')
        )

    def get_by_supervisor(self, supervisor_id: int) -> List[MeetingEntity]:
        from django.db.models import Q
        meetings = (
            Meeting.objects
            .filter(
                Q(supervisor_id=supervisor_id) |
                Q(examiner1_id=supervisor_id) |
                Q(examiner2_id=supervisor_id)
            )
            .select_related('team')
            .order_by('date', 'time')
        )
        return [self._to_entity(m) for m in meetings]

    def count_by_supervisor_and_team(self, supervisor_id: int, team_id: int) -> int:
        return Meeting.objects.filter(
            supervisor_id=supervisor_id, team_id=team_id
        ).count()

    def create(
        self,
        supervisor_id: int,
        team_id:       int,
        date:          datetime.date,
        time:          datetime.time,
        meeting_type:  MeetingType,
        topic:         str,
    ) -> MeetingEntity:
        m = Meeting.objects.create(
            supervisor_id=supervisor_id,
            team_id=team_id,
            date=date,
            time=time,
            meeting_type=meeting_type.value,
            topic=topic,
        )
        m.refresh_from_db()
        return self._to_entity(m)

    @staticmethod
    def _to_entity(m: Meeting) -> MeetingEntity:
        return MeetingEntity(
            id=m.pk,
            supervisor_id=m.supervisor_id,
            team_id=m.team_id,
            team_name=m.team.name if m.team_id else '',
            meeting_type=MeetingType(m.meeting_type),
            date=m.date,
            time=m.time,
            topic=m.topic or '',
            created_at=m.created_at,
        )


# ── Grading Reports ───────────────────────────────────────────────────────────

class DjangoGradingReportRepository(IGradingReportRepository):

    def get_by_supervisor(self, supervisor_id: int) -> List[GradingReportEntity]:
        from django.db.models import Q
        examiner_team_ids = Meeting.objects.filter(
            Q(examiner1_id=supervisor_id) | Q(examiner2_id=supervisor_id)
        ).values_list('team_id', flat=True)
        reports = (
            GradingReport.objects
            .filter(Q(supervisor_id=supervisor_id) | Q(team_id__in=examiner_team_ids))
            .select_related('team')
            .distinct()
        )
        return [self._to_entity(r) for r in reports]

    def create(self, entity: GradingReportEntity) -> GradingReportEntity:
        defaults = {
            'supervisor_id': entity.supervisor_id,
            'chief_grade':   entity.grade.chief_grade,
            'feedback':      entity.feedback,
        }
        # Only update examiner grades when explicitly provided (don't overwrite existing ones with None)
        if entity.grade.examiner_one_grade is not None:
            defaults['examiner_one_grade'] = entity.grade.examiner_one_grade
        if entity.grade.examiner_two_grade is not None:
            defaults['examiner_two_grade'] = entity.grade.examiner_two_grade
        r, _ = GradingReport.objects.update_or_create(
            team_id=entity.team_id,
            phase=entity.phase.value,
            defaults=defaults,
        )
        return self._to_entity(r)

    @staticmethod
    def _to_entity(r: GradingReport) -> GradingReportEntity:
        grade = WeightedGrade(
            chief_grade=float(r.chief_grade) if r.chief_grade is not None else 0.0,
            examiner_one_grade=float(r.examiner_one_grade) if r.examiner_one_grade is not None else None,
            examiner_two_grade=float(r.examiner_two_grade) if r.examiner_two_grade is not None else None,
        )
        return GradingReportEntity(
            id=r.pk,
            supervisor_id=r.supervisor_id,
            team_id=r.team_id,
            team_name=r.team.name if r.team_id else '',
            phase=GradingPhase(r.phase),
            grade=grade,
            feedback=r.feedback or '',
            created_at=r.created_at,
        )


# ── Supervision Requests ──────────────────────────────────────────────────────

class DjangoSupervisorRequestRepository(ISupervisorRequestRepository):

    def get_pending_for_supervisor(
        self, supervisor_id: int
    ) -> List[SupervisorRequestEntity]:
        reqs = (
            SupervisorRequest.objects
            .filter(target_supervisor_id=supervisor_id, status='pending')
            .select_related('team', 'leader')
            .order_by('-created_at')
        )
        return [self._to_entity(r) for r in reqs]

    def get_by_id(self, request_id: int) -> Optional[SupervisorRequestEntity]:
        try:
            r = SupervisorRequest.objects.select_related('team', 'leader').get(pk=request_id)
            return self._to_entity(r)
        except SupervisorRequest.DoesNotExist:
            return None

    def approve(
        self,
        request_id:    int,
        supervisor_id: int,
    ) -> Optional[SupervisorRequestEntity]:
        try:
            r = SupervisorRequest.objects.select_related('team').get(
                pk=request_id,
                target_supervisor_id=supervisor_id,
            )
            r.status      = 'approved'
            r.approved_by_id = supervisor_id
            r.decided_at  = timezone.now()
            r.save()
            return self._to_entity(r)
        except SupervisorRequest.DoesNotExist:
            return None

    def forward_or_reject(
        self,
        request_id:         int,
        next_supervisor_id: Optional[int],
        next_index:         int,
    ) -> Optional[SupervisorRequestEntity]:
        try:
            r = SupervisorRequest.objects.select_related('team').get(pk=request_id)
            r.decided_at = timezone.now()

            if next_supervisor_id is not None:
                r.current_index       = next_index
                r.target_supervisor_id = next_supervisor_id
                r.status              = 'pending'
            else:
                r.status = 'rejected'

            r.save()
            return self._to_entity(r)
        except SupervisorRequest.DoesNotExist:
            return None

    @staticmethod
    def _to_entity(r: SupervisorRequest) -> SupervisorRequestEntity:
        return SupervisorRequestEntity(
            id=r.pk,
            team_id=r.team_id,
            team_name=r.team.name if r.team_id else '',
            project_idea=r.project_idea,
            leader_id=r.leader_id,
            leader_name=r.leader.display_name if r.leader_id else '',
            preferences=r.preferences or [],
            current_index=r.current_index,
            target_supervisor_id=r.target_supervisor_id,
            status=RequestStatus(r.status),
            created_at=r.created_at,
        )


# ── Team Files ────────────────────────────────────────────────────────────────

class DjangoTeamFileRepository(ITeamFileRepository):

    def get_for_supervisor_teams(self, supervisor_id: int) -> List[TeamFileEntity]:
        files = (
            TeamFile.objects
            .filter(team__assigned_supervisor_id=supervisor_id)
            .select_related('team', 'uploader')
            .order_by('-created_at')
        )
        return [self._to_entity(f) for f in files]

    def get_by_id(self, file_id: int) -> Optional[TeamFileEntity]:
        try:
            f = TeamFile.objects.select_related('team', 'uploader').get(pk=file_id)
            return self._to_entity(f)
        except TeamFile.DoesNotExist:
            return None

    def delete(self, file_id: int) -> bool:
        deleted, _ = TeamFile.objects.filter(pk=file_id).delete()
        return deleted > 0

    @staticmethod
    def _to_entity(f: TeamFile) -> TeamFileEntity:
        return TeamFileEntity(
            id=f.pk,
            team_id=f.team_id,
            team_name=f.team.name if f.team_id else '',
            uploader_id=f.uploader_id or 0,
            uploader_name=f.uploader.display_name if f.uploader else '',
            file_name=f.file_name,
            description=f.description or '',
            file_path=f.file.name if f.file else '',
            created_at=f.created_at,
        )


# ── Notifications ─────────────────────────────────────────────────────────────

class DjangoNotificationRepository(INotificationRepository):

    def get_for_user(self, user_id: int) -> List[NotificationEntity]:
        notifs = (
            Notification.objects
            .filter(recipient_id=user_id)
            .order_by('-created_at')
        )
        return [self._to_entity(n) for n in notifs]

    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        updated = Notification.objects.filter(
            pk=notification_id, recipient_id=user_id
        ).update(is_read=True)
        return updated > 0

    def delete(self, notification_id: int, user_id: int) -> bool:
        deleted, _ = Notification.objects.filter(
            pk=notification_id, recipient_id=user_id
        ).delete()
        return deleted > 0

    def create(
        self,
        recipient_id: int,
        title:        str,
        message:      str,
        notif_type:   str,
        team_name:    str = '',
    ) -> NotificationEntity:
        n = Notification.objects.create(
            recipient_id=recipient_id,
            title=title,
            message=message,
            notif_type=notif_type,
            team_name=team_name,
        )
        return self._to_entity(n)

    @staticmethod
    def _to_entity(n: Notification) -> NotificationEntity:
        return NotificationEntity(
            id=n.pk,
            recipient_id=n.recipient_id,
            title=n.title,
            message=n.message,
            notif_type=n.notif_type,
            team_name=n.team_name,
            is_read=n.is_read,
            created_at=n.created_at,
        )
