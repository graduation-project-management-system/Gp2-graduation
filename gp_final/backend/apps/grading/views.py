from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.teams.models import Team
from apps.notifications.utils import push_notification
from .models import GradingReport
from .serializers import (
    GradingReportSerializer, GradingReportCreateSerializer,
    GradePreviewSerializer, ExaminerGradeSerializer,
)


# ── Preview (no save) ─────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grade_preview(request):
    """
    POST /api/v1/grading/preview/
    Body: { chief_grade, examiner_one_grade, examiner_two_grade }
    Returns computed final_grade using the 50/25/25 formula.
    """
    serializer = GradePreviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data
    weights = getattr(settings, 'GRADING_WEIGHTS', {
        'chief_supervisor': 0.50,
        'examiner_one':     0.25,
        'examiner_two':     0.25,
    })
    final = (
        float(d['chief_grade'])        * weights['chief_supervisor'] +
        float(d['examiner_one_grade']) * weights['examiner_one'] +
        float(d['examiner_two_grade']) * weights['examiner_two']
    )
    return Response({'final_grade': round(final, 2)})


# ── Create report ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_report(request):
    """
    POST /api/v1/grading/
    Multipart form (supports file upload):
      team_id, phase, chief_grade, examiner_one_grade, examiner_two_grade, feedback, archived_file
    Supervisor only; team must be assigned to them.
    """
    if request.user.role != 'supervisor':
        return Response({'error': 'Only supervisors can submit grading reports.'}, status=403)

    serializer = GradingReportCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    team = get_object_or_404(Team, pk=data.pop('team_id'))
    if team.assigned_supervisor != request.user:
        return Response({'error': 'This team is not assigned to you.'}, status=403)

    report, _ = GradingReport.objects.update_or_create(
        team=team, phase=data['phase'],
        defaults={'supervisor': request.user, 'chief_grade': data['chief_grade'],
                  'feedback': data.get('feedback', ''),
                  **({'archived_file': data['archived_file']} if data.get('archived_file') else {})},
    )

    # Notify every team member
    for member in team.members.all():
        push_notification(
            recipient_id=member.pk,
            title='Grade published',
            message=(
                f'Your {report.phase} grade has been published. '
                f'Final: {report.final_grade}/100.'
            ),
            notif_type='grade_published',
            team_name=team.name,
        )

    push_notification(
        recipient_id=request.user.pk,
        title='Report archived',
        message=f'Report for {team.name} ({report.phase}) saved successfully.',
        notif_type='report_saved',
        team_name=team.name,
    )

    return Response(
        GradingReportSerializer(report, context={'request': request}).data,
        status=201,
    )


# ── List reports ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_reports(request):
    """
    GET /api/v1/grading/
    Optional query params: ?team=<name>&phase=<Proposal|Midterm|Final>
    """
    user = request.user
    if user.role == 'supervisor':
        from apps.meetings.models import Meeting
        from django.db.models import Q
        examiner_team_ids = Meeting.objects.filter(
            Q(examiner1=user) | Q(examiner2=user)
        ).values_list('team_id', flat=True)
        qs = GradingReport.objects.filter(
            Q(supervisor=user) | Q(team_id__in=examiner_team_ids)
        ).distinct()
    elif user.role == 'student':
        teams = Team.objects.filter(members=user)
        qs    = GradingReport.objects.filter(team__in=teams)
    else:
        qs = GradingReport.objects.all()

    team_q  = request.query_params.get('team')
    phase_q = request.query_params.get('phase')
    if team_q:
        qs = qs.filter(team__name__icontains=team_q)
    if phase_q:
        qs = qs.filter(phase=phase_q)

    return Response(GradingReportSerializer(qs, many=True, context={'request': request}).data)


# ── Examiner grade submission ─────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_examiner_grade(request):
    """
    POST /api/v1/grading/examiner-grade/
    Body: { team_id, phase, grade }
    The logged-in supervisor must be examiner1 or examiner2 for the team.
    """
    if request.user.role != 'supervisor':
        return Response({'error': 'Only supervisors can submit grades.'}, status=403)

    s = ExaminerGradeSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data

    from apps.meetings.models import Meeting
    from django.db.models import Q
    meeting = Meeting.objects.filter(
        team_id=d['team_id']
    ).filter(
        Q(examiner1=request.user) | Q(examiner2=request.user)
    ).first()

    if not meeting:
        return Response({'error': 'You are not an examiner for this team.'}, status=403)

    team = get_object_or_404(Team, pk=d['team_id'])
    report, _ = GradingReport.objects.get_or_create(
        team=team, phase=d['phase'],
        defaults={'supervisor': team.assigned_supervisor or request.user, 'chief_grade': 0},
    )

    if meeting.examiner1_id == request.user.pk:
        report.examiner_one_grade = d['grade']
    else:
        report.examiner_two_grade = d['grade']
    report.save()

    # Check if both examiners have now submitted → final grade is ready
    final = report.final_grade
    if final is not None:
        # Notify team members
        for member in team.members.all():
            push_notification(
                recipient_id=member.pk,
                title='Final grade published',
                message=f'All grades for {report.phase} are submitted. Final grade: {final:.1f}/100.',
                notif_type='grade_published',
                team_name=team.name,
            )
        # Notify chief supervisor
        if team.assigned_supervisor:
            push_notification(
                recipient_id=team.assigned_supervisor.pk,
                title='Grading complete',
                message=f'Both examiners submitted grades for {team.name} ({report.phase}). Final: {final:.1f}/100.',
                notif_type='grade_published',
                team_name=team.name,
            )
    else:
        # Notify chief supervisor that one examiner submitted
        if team.assigned_supervisor:
            push_notification(
                recipient_id=team.assigned_supervisor.pk,
                title='Examiner grade submitted',
                message=f'{request.user.display_name} submitted their examiner grade for {team.name} ({report.phase}).',
                notif_type='grade_published',
                team_name=team.name,
            )

    return Response(GradingReportSerializer(report, context={'request': request}).data, status=200)


# ── Examiner teams list ───────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def examiner_teams(request):
    """
    GET /api/v1/grading/examiner-teams/
    Returns teams where the logged-in supervisor is an examiner.
    """
    if request.user.role != 'supervisor':
        return Response([], status=200)

    from apps.meetings.models import Meeting
    from django.db.models import Q
    meetings = Meeting.objects.filter(
        Q(examiner1=request.user) | Q(examiner2=request.user)
    ).select_related('team')

    result = []
    for m in meetings:
        if not m.team:
            continue
        result.append({
            'team_id':   m.team.id,
            'team_name': m.team.name,
            'position':  1 if m.examiner1_id == request.user.pk else 2,
        })
    return Response(result)
