"""
Interface Layer — thin REST views.
Each view does only three things:
  1. Validate input (using input serializers).
  2. Call the appropriate use case.
  3. Serialize the domain entity and return a Response.
No business logic lives here.
"""
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.requests.models import SupervisorRequest as SupervisorRequestModel
from apps.requests.serializers import SupervisorRequestSerializer

from ..application.use_cases import (
    ManageAvailabilityUseCase,
    ScheduleMeetingUseCase,
    GetMeetingsUseCase,
    DecideSupervisionRequestUseCase,
    SubmitGradingReportUseCase,
    ManageFilesUseCase,
    GetNotificationsUseCase,
)
from ..infrastructure.django_repositories import (
    DjangoTeamRepository,
    DjangoAvailabilitySlotRepository,
    DjangoMeetingRepository,
    DjangoGradingReportRepository,
    DjangoSupervisorRequestRepository,
    DjangoTeamFileRepository,
    DjangoNotificationRepository,
)
from ..domain.value_objects import MeetingType, SlotMode, GradingPhase
from .serializers import (
    AvailabilitySlotOutputSerializer,
    MeetingOutputSerializer,
    GradingReportOutputSerializer,
    SupervisorRequestOutputSerializer,
    TeamFileOutputSerializer,
    NotificationOutputSerializer,
    AddSlotInputSerializer,
    BookMeetingInputSerializer,
    GradingReportInputSerializer,
    DecideRequestInputSerializer,
)


def _supervisor_only(request):
    """Guard: returns a 403 Response if the caller is not a supervisor."""
    if request.user.role != UserRole.SUPERVISOR:
        return Response({'error': 'Supervisors only.'}, status=403)
    return None


# ── Availability Slots ────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def availability_slots(request):
    """
    GET  /api/v1/supervisor/slots/   → list own slots
    POST /api/v1/supervisor/slots/   → add a new slot
    """
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = ManageAvailabilityUseCase(DjangoAvailabilitySlotRepository())

    if request.method == 'GET':
        slots = uc.list_slots(request.user.pk)
        return Response(
            AvailabilitySlotOutputSerializer(slots, many=True).data
        )

    s = AddSlotInputSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    try:
        slot = uc.add_slot(
            supervisor_id=request.user.pk,
            date=d['date'],
            start_time=d['start_time'],
            end_time=d['end_time'],
            mode=SlotMode(d['mode']),
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    return Response(AvailabilitySlotOutputSerializer(slot).data, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_slot(request, pk):
    """DELETE /api/v1/supervisor/slots/<pk>/"""
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = ManageAvailabilityUseCase(DjangoAvailabilitySlotRepository())
    try:
        uc.remove_slot(request.user.pk, pk)
    except ValueError as e:
        return Response({'error': str(e)}, status=404)

    return Response({'detail': 'Slot deleted.'}, status=204)


# ── Meetings ──────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_meeting(request):
    """
    POST /api/v1/supervisor/meetings/book/
    Body: { team_id, meeting_type, topic }
    """
    guard = _supervisor_only(request)
    if guard:
        return guard

    s = BookMeetingInputSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data

    uc = ScheduleMeetingUseCase(
        team_repo=DjangoTeamRepository(),
        meeting_repo=DjangoMeetingRepository(),
        slot_repo=DjangoAvailabilitySlotRepository(),
        notif_repo=DjangoNotificationRepository(),
    )

    try:
        with transaction.atomic():
            meeting = uc.execute(
                supervisor_id=request.user.pk,
                supervisor_name=request.user.display_name,
                team_id=d['team_id'],
                meeting_type=MeetingType(d['meeting_type']),
                topic=d['topic'],
            )
    except PermissionError as e:
        return Response({'error': str(e)}, status=403)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    return Response(MeetingOutputSerializer(meeting).data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def meeting_list(request):
    """GET /api/v1/supervisor/meetings/"""
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = GetMeetingsUseCase(DjangoMeetingRepository())
    meetings = uc.execute(request.user.pk)
    return Response(MeetingOutputSerializer(meetings, many=True).data)


# ── Supervision Requests ──────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervision_requests(request):
    """GET /api/v1/supervisor/requests/ → pending requests targeting this supervisor"""
    guard = _supervisor_only(request)
    if guard:
        return guard

    qs = SupervisorRequestModel.objects.filter(
        target_supervisor=request.user, status='pending'
    )
    return Response(SupervisorRequestSerializer(qs, many=True, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decide_request(request, pk):
    """
    POST /api/v1/supervisor/requests/<pk>/decide/
    Body: { decision: 'approve' | 'reject' }
    """
    guard = _supervisor_only(request)
    if guard:
        return guard

    s = DecideRequestInputSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    uc = DecideSupervisionRequestUseCase(
        request_repo=DjangoSupervisorRequestRepository(),
        team_repo=DjangoTeamRepository(),
        notif_repo=DjangoNotificationRepository(),
    )
    try:
        result = uc.decide(
            supervisor_id=request.user.pk,
            supervisor_name=request.user.display_name,
            request_id=pk,
            decision=s.validated_data['decision'],
        )
    except PermissionError as e:
        return Response({'error': str(e)}, status=403)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    return Response(SupervisorRequestOutputSerializer(result).data)


# ── Grading Reports ───────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def grading_reports(request):
    """
    GET  /api/v1/supervisor/grading/   → list reports submitted by this supervisor
    POST /api/v1/supervisor/grading/   → submit a new grading report
    """
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = SubmitGradingReportUseCase(
        grading_repo=DjangoGradingReportRepository(),
        team_repo=DjangoTeamRepository(),
        notif_repo=DjangoNotificationRepository(),
    )

    if request.method == 'GET':
        reports = uc.list_reports(request.user.pk)
        return Response(GradingReportOutputSerializer(reports, many=True).data)

    s = GradingReportInputSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data

    try:
        report = uc.submit(
            supervisor_id=request.user.pk,
            supervisor_name=request.user.display_name,
            team_id=d['team_id'],
            phase=GradingPhase(d['phase']),
            chief_grade=d['chief_grade'],
            examiner_one_grade=d['examiner_one_grade'],
            examiner_two_grade=d['examiner_two_grade'],
            feedback=d['feedback'],
        )
    except PermissionError as e:
        return Response({'error': str(e)}, status=403)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    return Response(GradingReportOutputSerializer(report).data, status=201)


# ── Grading Preview (utility — no domain state change) ────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grading_preview(request):
    """
    POST /api/v1/supervisor/grading/preview/
    Body: { chief_grade, examiner_one_grade, examiner_two_grade }
    Returns computed final_grade (50/25/25 weights) without saving.
    """
    from django.conf import settings as django_settings
    weights = getattr(django_settings, 'GRADING_WEIGHTS', {
        'chief_supervisor': 0.50,
        'examiner_one':     0.25,
        'examiner_two':     0.25,
    })
    try:
        chief = float(request.data.get('chief_grade', 0))
        e1    = float(request.data.get('examiner_one_grade', 0))
        e2    = float(request.data.get('examiner_two_grade', 0))
    except (TypeError, ValueError):
        return Response({'error': 'Invalid grade values.'}, status=400)

    final = (
        chief * weights['chief_supervisor'] +
        e1    * weights['examiner_one'] +
        e2    * weights['examiner_two']
    )
    return Response({'final_grade': round(final, 2)})


# ── Files ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def file_list(request):
    """GET /api/v1/supervisor/files/?team_id=<id>"""
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = ManageFilesUseCase(DjangoTeamFileRepository())
    files = uc.list_files(request.user.pk)

    team_id = request.query_params.get('team_id')
    if team_id:
        try:
            files = [f for f in files if f.team_id == int(team_id)]
        except (ValueError, TypeError):
            pass

    return Response(
        TeamFileOutputSerializer(files, many=True, context={'request': request}).data
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request, pk):
    """DELETE /api/v1/supervisor/files/<pk>/"""
    guard = _supervisor_only(request)
    if guard:
        return guard

    uc = ManageFilesUseCase(DjangoTeamFileRepository())
    try:
        uc.delete_file(request.user.pk, pk)
    except ValueError as e:
        return Response({'error': str(e)}, status=404)

    return Response({'detail': 'File deleted.'}, status=204)


# ── Notifications ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications(request):
    """GET /api/v1/supervisor/notifications/"""
    uc = GetNotificationsUseCase(DjangoNotificationRepository())
    notifs = uc.list(request.user.pk)
    return Response(NotificationOutputSerializer(notifs, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, pk):
    """PATCH /api/v1/supervisor/notifications/<pk>/read/"""
    uc = GetNotificationsUseCase(DjangoNotificationRepository())
    try:
        uc.mark_read(request.user.pk, pk)
    except ValueError as e:
        return Response({'error': str(e)}, status=404)
    return Response({'detail': 'Marked as read.'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    """DELETE /api/v1/supervisor/notifications/<pk>/"""
    uc = GetNotificationsUseCase(DjangoNotificationRepository())
    try:
        uc.delete(request.user.pk, pk)
    except ValueError as e:
        return Response({'error': str(e)}, status=404)
    return Response({'detail': 'Notification deleted.'}, status=204)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notif_unread_count(request):
    """GET /api/v1/supervisor/notifications/unread-count/"""
    from apps.notifications.models import Notification
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'unread_count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notif_mark_all_read(request):
    """POST /api/v1/supervisor/notifications/mark-all-read/"""
    from apps.notifications.models import Notification
    updated = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True)
    return Response({'marked_read': updated})
