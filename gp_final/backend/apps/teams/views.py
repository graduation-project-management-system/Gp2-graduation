import json
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.notifications.utils import push_notification
from .models import Team, ExamDate, MembershipRequest, SupervisionRequest
from .permissions import IsSupervisor, IsStudent, IsTeamLeader


def _supervisor_capacity_error(supervisor, current_team=None):
    max_teams = getattr(settings, 'MAX_TEAMS_PER_SUPERVISOR', 5)
    assigned = Team.objects.filter(assigned_supervisor=supervisor)
    if current_team is not None:
        assigned = assigned.exclude(pk=current_team.pk)
    if assigned.count() >= max_teams:
        return f'Supervisor {supervisor.display_name} is full ({max_teams}/{max_teams} teams).'
    return None


# ── List / Create teams ───────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def team_list_create(request):
    # استيراد داخلي لمنع الـ Circular Import والـ NameError
    from .serializers import TeamSerializer, TeamCreateSerializer

    if request.method == 'GET':
        user = request.user
        if user.role == UserRole.SUPERVISOR:
            teams = Team.objects.filter(assigned_supervisor=user)
        elif user.role == UserRole.ADMIN:
            teams = Team.objects.all()
        else:
            # student: إذا في team يرجع teamه، إذا ما في يرجع كل التيمات المتاحة
            user_team = Team.objects.filter(members=user).first()
            if user_team:
                teams = Team.objects.filter(id=user_team.id)
            else:
                teams = Team.objects.exclude(status__in=['disbanded', 'complete'])
        return Response(TeamSerializer(teams, many=True).data)

    # POST — students or admin
    if request.user.role == UserRole.ADMIN:
        # Use serializer for validation and member_ids support
        from .serializers import TeamSerializer, TeamCreateSerializer

        data = request.data.copy()
        # Accept 'description' as alias for 'project_description'
        if 'description' in data and 'project_description' not in data:
            data['project_description'] = data['description']

        serializer = TeamCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        supervisor_to_assign = None
        sup_id = request.data.get('supervisor_id')
        if sup_id:
            from apps.accounts.models import User as UserModel
            try:
                supervisor_to_assign = UserModel.objects.get(pk=sup_id, role='supervisor')
            except UserModel.DoesNotExist:
                supervisor_to_assign = None
            if supervisor_to_assign:
                capacity_error = _supervisor_capacity_error(supervisor_to_assign)
                if capacity_error:
                    return Response({'error': capacity_error}, status=400)
        team = serializer.save()
        # Assign supervisor if provided
        if supervisor_to_assign:
            team.assigned_supervisor = supervisor_to_assign
            team.save(update_fields=['assigned_supervisor'])
        return Response(TeamSerializer(team).data, status=201)

    if request.user.role != UserRole.STUDENT:
        return Response({'error': 'Only students can create teams.'}, status=400)

    if Team.objects.filter(members=request.user).exists():
        return Response({'error': 'You already belong to a team.'}, status=400)

    # Accept 'description' as alias for 'project_description'
    data = request.data.copy()
    if 'description' in data and 'project_description' not in data:
        data['project_description'] = data['description']

    serializer = TeamCreateSerializer(data=data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    team = serializer.save()

    # Cancel any pending join requests this student sent to other teams
    cancelled = MembershipRequest.objects.filter(
        student=request.user, status='pending'
    ).update(status='rejected')
    if cancelled:
        push_notification(
            recipient_id=request.user.pk,
            title='Join requests cancelled',
            message=f'Your {cancelled} pending join request(s) were cancelled because you created a new team.',
            notif_type='general',
        )

    return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)


# ── Retrieve / Update / Delete a single team ─────────────────────────────────
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def team_detail(request, pk):
    """
    GET    /api/v1/teams/<pk>/   → team detail
    PATCH  /api/v1/teams/<pk>/   → update (leader or supervisor)
    DELETE /api/v1/teams/<pk>/   → disband (leader only)
    """
    from .serializers import TeamSerializer, TeamUpdateSerializer
    team = get_object_or_404(Team, pk=pk)

    if request.method == 'GET':
        return Response(TeamSerializer(team).data)

    if request.method == 'PATCH':
        is_admin = request.user.role == UserRole.ADMIN
        is_leader = team.leader == request.user
        is_supervisor = team.assigned_supervisor == request.user
        if not (is_admin or is_leader or is_supervisor):
            return Response({'error': 'Not authorised.'}, status=403)

        # Admin-only fields: name, supervisor assignment
        if is_admin:
            if 'name' in request.data and request.data['name']:
                team.name = request.data['name']
            # Use sentinel to detect explicit null vs absent key
            _ABSENT = object()
            supervisor_id = request.data.get('supervisor_id', _ABSENT)
            if supervisor_id is not _ABSENT:
                from apps.accounts.models import User as UserModel
                if not supervisor_id:          # null, 0, or ""
                    team.assigned_supervisor = None
                else:
                    try:
                        supervisor = UserModel.objects.get(pk=supervisor_id, role='supervisor')
                        capacity_error = _supervisor_capacity_error(supervisor, current_team=team)
                        if capacity_error:
                            return Response({'error': capacity_error}, status=400)
                        if team.assigned_supervisor_id != supervisor.pk:
                            team.assigned_supervisor = supervisor
                            # Notify team members about new supervisor
                            for member in team.members.all():
                                push_notification(
                                    recipient_id=member.pk,
                                    title='Supervisor assigned',
                                    message=f'Dr. {supervisor.display_name} has been assigned as your supervisor by admin.',
                                    notif_type='supervisor_assigned',
                                    team_name=team.name,
                                )
                        else:
                            team.assigned_supervisor = supervisor
                    except UserModel.DoesNotExist:
                        pass

        serializer = TeamUpdateSerializer(team, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TeamSerializer(team).data)

    # DELETE — admin can delete any team, leader can disband their own
    if request.user.role == UserRole.ADMIN:
        team.delete()
        return Response({'detail': 'Team deleted.', 'message': 'Team deleted successfully.'})
    if team.leader != request.user:
        return Response({'error': 'Only the team leader can disband the team.'}, status=403)
    team.status = 'disbanded'
    team.save()
    return Response({'detail': 'Team disbanded.'})


# ── Admin: approve / reject team ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_team(request, pk):
    """POST /api/v1/teams/<pk>/approve/ — admin only"""
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Admin only.'}, status=403)
    team = get_object_or_404(Team, pk=pk)
    team.status = 'active'
    team.save(update_fields=['status'])
    for member in team.members.all():
        push_notification(
            recipient_id=member.pk,
            title='Team approved',
            message=f'Your team "{team.name}" has been approved by admin.',
            notif_type='general',
            team_name=team.name,
        )
    return Response({'success': True, 'message': f'Team "{team.name}" approved.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_team(request, pk):
    """POST /api/v1/teams/<pk>/reject/ — admin only"""
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Admin only.'}, status=403)
    team = get_object_or_404(Team, pk=pk)
    team.status = 'disbanded'
    team.save(update_fields=['status'])
    for member in team.members.all():
        push_notification(
            recipient_id=member.pk,
            title='Team rejected',
            message=f'Your team "{team.name}" has been rejected by admin.',
            notif_type='general',
            team_name=team.name,
        )
    return Response({'success': True, 'message': f'Team "{team.name}" rejected.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_team(request, pk):
    """POST /api/v1/teams/<pk>/archive/ — admin only, only complete teams."""
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Admin only.'}, status=403)
    team = get_object_or_404(Team, pk=pk)
    if team.status != 'complete':
        return Response({'error': 'Only completed teams can be archived.'}, status=400)
    team.is_archived = True
    team.archive_date = timezone.now()
    team.save(update_fields=['is_archived', 'archive_date'])
    return Response({'success': True, 'message': f'Team "{team.name}" archived.'})


# ── Exam dates ────────────────────────────────────────────────────────────────
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def team_exam_dates(request, pk):
    """
    GET    /api/v1/teams/<pk>/exam-dates/        → list exam dates
    POST   /api/v1/teams/<pk>/exam-dates/        → add exam date  { date }
    DELETE /api/v1/teams/<pk>/exam-dates/<date>/ → remove exam date
    """
    from .serializers import ExamDateAddSerializer
    team = get_object_or_404(Team, pk=pk)

    if request.method == 'GET':
        from .serializers import ExamDateSerializer
        return Response(ExamDateSerializer(team.exam_dates.all(), many=True).data)

    if request.method == 'POST':
        if team.assigned_supervisor != request.user and request.user.role != UserRole.ADMIN:
            return Response({'error': 'Only the assigned supervisor can add exam dates.'}, status=403)
        serializer = ExamDateAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ExamDate.objects.get_or_create(team=team, date=serializer.validated_data['date'])
        return Response({'detail': 'Exam date added.'}, status=201)

    # DELETE — body: { date }
    date = request.data.get('date')
    ExamDate.objects.filter(team=team, date=date).delete()
    return Response({'detail': 'Exam date removed.'})


# ── Membership requests ───────────────────────────────────────────────────────
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def membership_requests(request, pk):
    """
    GET    /api/v1/teams/<pk>/join-requests/   → leader sees pending requests
    POST   /api/v1/teams/<pk>/join-requests/   → student sends a join request
    DELETE /api/v1/teams/<pk>/join-requests/   → student cancels their own pending request
    """
    from .serializers import MembershipRequestSerializer
    team = get_object_or_404(Team, pk=pk)

    if request.method == 'GET':
        # All team members (and admin) can view pending join requests
        is_member = team.members.filter(pk=request.user.pk).exists()
        is_leader = team.leader == request.user
        if not (is_member or is_leader or request.user.role == UserRole.ADMIN):
            return Response({'error': 'Not a team member.'}, status=403)
        reqs = MembershipRequest.objects.filter(team=team, status='pending').select_related('student').prefetch_related('yes_voters', 'no_voters')
        data = MembershipRequestSerializer(reqs, many=True, context={'request': request}).data
        for item in data:
            item['can_decide'] = is_leader
        return Response(data)

    if request.method == 'DELETE':
        req = MembershipRequest.objects.filter(team=team, student=request.user, status='pending').first()
        if not req:
            return Response({'error': 'No pending request found.'}, status=404)
        req.delete()
        return Response({'detail': 'Join request cancelled successfully.'})

    # POST
    if request.user.role != UserRole.STUDENT:
        return Response({'error': 'Only students can send join requests.'}, status=400)
    if team.status in ('disbanded', 'complete', 'locked', 'expired'):
        return Response({'detail': 'This team is not accepting members.'}, status=400)

    # Block only if there's an active (pending/approved) request
    existing = MembershipRequest.objects.filter(team=team, student=request.user).first()
    if existing:
        if existing.status == 'pending':
            return Response({'error': 'You already have a pending request for this team.'}, status=400)
        if existing.status == 'approved':
            return Response({'error': 'You are already a member of this team.'}, status=400)
        # Rejected/cancelled — delete old record so we can create a fresh one
        existing.delete()

    with transaction.atomic():
        locked_team = Team.objects.select_for_update().get(pk=team.pk)
        if locked_team.members.count() >= 5:
            return Response({'detail': 'Team is full.'}, status=400)
        req = MembershipRequest.objects.create(team=locked_team, student=request.user)

    push_notification(
        recipient_id=team.leader_id,
        title='New join request',
        message=f'{request.user.display_name} wants to join {team.name}.',
        notif_type='join_request',
    )
    return Response(MembershipRequestSerializer(req).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decide_membership(request, pk, req_id):
    """
    POST /api/v1/teams/<pk>/join-requests/<req_id>/decide/
    Body: { decision: 'approve' | 'reject' }

    Any team member may cast one vote. Decision is final when strict majority (>50%)
    of current members vote the same way.
    """
    from .serializers import MembershipRequestSerializer
    team = get_object_or_404(Team, pk=pk)

    # Allow any team member to vote
    is_member = team.members.filter(pk=request.user.pk).exists()
    is_leader = team.leader_id == request.user.pk
    if not (is_member or is_leader):
        return Response({'error': 'Only team members can vote.'}, status=403)

    req = get_object_or_404(MembershipRequest, pk=req_id, team=team, status='pending')

    decision = request.data.get('decision')
    if decision not in ('approve', 'reject'):
        return Response({'error': "decision must be 'approve' or 'reject'."}, status=400)

    # Prevent double-voting
    already_voted = (
        req.yes_voters.filter(pk=request.user.pk).exists() or
        req.no_voters.filter(pk=request.user.pk).exists()
    )
    if already_voted:
        return Response({'error': 'You have already voted on this request.'}, status=400)

    # Record the vote
    if decision == 'approve':
        req.yes_voters.add(request.user)
    else:
        req.no_voters.add(request.user)

    # Recalculate after vote
    total_members = team.members.count()
    yes_count = req.yes_voters.count()
    no_count  = req.no_voters.count()
    threshold = total_members / 2   # strict majority = > 50%

    if yes_count > threshold:
        # Majority approved → add student to team
        with transaction.atomic():
            locked_team = Team.objects.select_for_update().get(pk=team.pk)
            if locked_team.members.count() >= 5:
                return Response({'error': 'Team is full.'}, status=400)
            req.status = 'approved'
            req.save()
            locked_team.members.add(req.student)
        # Cancel all other pending requests from the same student
        MembershipRequest.objects.filter(
            student=req.student, status='pending'
        ).exclude(pk=req.pk).update(status='rejected')
        push_notification(
            recipient_id=req.student_id,
            title='Join request approved',
            message=f'Majority voted yes. You have been added to {team.name}!',
            notif_type='join_approved',
        )
        new_status = 'accepted'

    elif no_count > threshold:
        # Majority rejected → reject the request
        req.status = 'rejected'
        req.save()
        push_notification(
            recipient_id=req.student_id,
            title='Join request rejected',
            message=f'Majority voted no. Your request to join {team.name} was declined.',
            notif_type='join_rejected',
        )
        new_status = 'rejected'

    else:
        # No majority yet — vote recorded, still pending
        new_status = 'pending'

    return Response({
        'new_status': new_status,
        'yes_count':  yes_count,
        'no_count':   no_count,
        'required':   int(threshold) + 1,
        'total':      total_members,
        'request':    MembershipRequestSerializer(req, context={'request': request}).data,
    })


# ── Supervisor comment on a team ──────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request, pk):
    """
    POST /api/v1/teams/<pk>/comment/
    Body: { comment }
    Only the assigned supervisor may post comments.
    """
    team = get_object_or_404(Team, pk=pk)
    if team.assigned_supervisor != request.user:
        return Response({'error': 'Only the assigned supervisor can comment.'}, status=403)

    comment = (request.data.get('comment') or '').strip()
    if not comment:
        return Response({'error': 'Comment cannot be empty.'}, status=400)

    for member in team.members.all():
        push_notification(
            recipient_id=member.id,
            title='Supervisor comment',
            message=f'Dr. {request.user.display_name}: {comment}',
            notif_type='supervisor_comment',
            team_name=team.name,
        )
    return Response({'detail': 'Comment sent to all team members.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_team(request, pk):
    team = get_object_or_404(Team, pk=pk)

    # التأكد إنه عضو بالتيم
    if request.user not in team.members.all():
        return Response(
            {'error': 'You are not a member of this team.'},
            status=400
        )

    # ── إذا الشخص هو الليدر ─────────────────────────
    if team.leader == request.user:

        # كل الأعضاء غير الليدر
        remaining_members = team.members.exclude(id=request.user.id)

        # إذا ما في أعضاء غيره → احذف التيم
        if not remaining_members.exists():
            team.delete()
            return Response({'detail': 'Leader left and the team was deleted.'})

        # إذا في أعضاء → نقل القيادة
        new_leader = remaining_members.first()
        team.members.remove(request.user)
        team.leader = new_leader
        team.save()

        # Notify remaining members about new leader
        for member in team.members.all():
            push_notification(
                recipient_id=member.pk,
                title='New team leader',
                message=f'{request.user.display_name} left. {new_leader.display_name} is now the team leader.',
                notif_type='general',
                team_name=team.name,
            )

        return Response({'detail': f'Leadership transferred to {new_leader.display_name}.'})

    # ── عضو عادي ────────────────────────────────────
    team.members.remove(request.user)

    # Notify team leader
    if team.leader:
        push_notification(
            recipient_id=team.leader.pk,
            title='Member left',
            message=f'{request.user.display_name} has left {team.name}.',
            notif_type='general',
            team_name=team.name,
        )

    return Response({'detail': 'You have left the team.'})


# ── Cancel own join request ───────────────────────────────────────────────────
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def cancel_join_request(request, req_id):
    """POST or DELETE /api/v1/teams/join-requests/<req_id>/cancel/ — student cancels their own pending request."""
    req = get_object_or_404(MembershipRequest, pk=req_id, student=request.user)
    if req.status != 'pending':
        return Response({'error': 'Only pending requests can be cancelled.'}, status=400)
    req.delete()
    return Response({'detail': 'Join request cancelled successfully.'})


# ── My team (returns user's team or 404) ─────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_team(request):
    """GET /api/v1/teams/my/ — returns the current user's team or 404."""
    from .serializers import TeamSerializer
    team = Team.objects.filter(members=request.user).first()
    if not team:
        return Response({'detail': 'You are not in any team.'}, status=404)
    return Response(TeamSerializer(team).data)


# ── Vote on a join request by request ID only ─────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vote_join_request(request, req_id):
    """POST /api/v1/teams/join-requests/<req_id>/vote/  { vote: 'yes'|'no' }"""
    from .serializers import MembershipRequestSerializer
    req = get_object_or_404(MembershipRequest, pk=req_id, status='pending')
    team = req.team

    is_member = team.members.filter(pk=request.user.pk).exists()
    is_leader = team.leader_id == request.user.pk
    if not (is_member or is_leader):
        return Response({'error': 'Only team members can vote.'}, status=403)

    vote = request.data.get('vote')
    if vote not in ('yes', 'no'):
        return Response({'error': "vote must be 'yes' or 'no'."}, status=400)

    already_voted = (
        req.yes_voters.filter(pk=request.user.pk).exists() or
        req.no_voters.filter(pk=request.user.pk).exists()
    )
    if already_voted:
        return Response({'error': 'You have already voted.'}, status=400)

    if vote == 'yes':
        req.yes_voters.add(request.user)
    else:
        req.no_voters.add(request.user)

    total_members = team.members.count()
    yes_count = req.yes_voters.count()
    no_count  = req.no_voters.count()
    threshold = total_members / 2

    if yes_count > threshold:
        with transaction.atomic():
            locked_team = Team.objects.select_for_update().get(pk=team.pk)
            if locked_team.members.count() >= 5:
                return Response({'error': 'Team is full.'}, status=400)
            req.status = 'approved'
            req.save()
            locked_team.members.add(req.student)
        # Cancel all other pending requests from the same student
        MembershipRequest.objects.filter(
            student=req.student, status='pending'
        ).exclude(pk=req.pk).update(status='rejected')
        push_notification(
            recipient_id=req.student_id,
            title='Join request approved',
            message=f'You have been added to {team.name}!',
            notif_type='join_approved',
        )
        new_status = 'accepted'
    elif no_count > threshold:
        req.status = 'rejected'
        req.save()
        push_notification(
            recipient_id=req.student_id,
            title='Join request rejected',
            message=f'Your request to join {team.name} was not approved.',
            notif_type='join_rejected',
        )
        new_status = 'rejected'
    else:
        new_status = 'pending'

    return Response({
        'new_status': new_status,
        'yes_count':  yes_count,
        'no_count':   no_count,
        'required':   int(threshold) + 1,
        'total':      total_members,
    })


# ── Supervisor list ───────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_list(request):
    """GET /api/v1/teams/supervisors/"""
    from apps.accounts.models import User
    sups = User.objects.filter(role='supervisor')
    data = [{'id': s.id, 'display_name': s.display_name, 'email': s.email,
              'department': getattr(s, 'department', ''), 'expertise': getattr(s, 'expertise', '')}
            for s in sups]
    return Response(data)


# ── Create a supervision request (one per supervisor, max 3 per team) ─────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_supervision_request(request, pk):
    """POST /api/v1/teams/<pk>/supervisor-request/  { supervisor_id, priority }"""
    from apps.accounts.models import User
    team = get_object_or_404(Team, pk=pk)
    if team.leader != request.user and request.user.role != UserRole.ADMIN:
        return Response({'detail': 'Only the team leader can send supervisor requests.'}, status=403)
    if SupervisionRequest.objects.filter(team=team).count() >= 3:
        return Response({'detail': 'Maximum 3 supervisor requests allowed per team.'}, status=400)
    supervisor_id = request.data.get('supervisor_id')
    priority = request.data.get('priority', 1)
    supervisor = get_object_or_404(User, pk=supervisor_id, role='supervisor')
    if SupervisionRequest.objects.filter(team=team, supervisor=supervisor).exists():
        return Response({'detail': 'Already sent a request to this supervisor.'}, status=400)
    req = SupervisionRequest.objects.create(team=team, supervisor=supervisor, priority=priority)
    push_notification(
        recipient_id=supervisor.pk,
        title='New supervision request',
        message=f'{team.name} wants you as their supervisor.',
        notif_type='supervisor_request',
        team_name=team.name,
    )
    return Response({'id': req.pk, 'status': req.status, 'priority': req.priority,
                     'supervisor': supervisor.pk, 'team': team.pk}, status=201)


# ── List a team's supervision requests ────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def team_supervision_requests(request, pk):
    """GET /api/v1/teams/<pk>/supervisor-requests/"""
    team = get_object_or_404(Team, pk=pk)
    reqs = SupervisionRequest.objects.filter(team=team)
    data = [{'id': r.pk, 'status': r.status, 'priority': r.priority,
              'supervisor': r.supervisor_id, 'team': team.pk} for r in reqs]
    return Response(data)


# ── Supervisor inbox ──────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_inbox(request):
    """GET /api/v1/teams/supervisor-inbox/"""
    if request.user.role != UserRole.SUPERVISOR:
        return Response({'error': 'Supervisors only.'}, status=403)
    reqs = SupervisionRequest.objects.filter(supervisor=request.user)
    data = [{'id': r.pk, 'status': r.status, 'priority': r.priority, 'team': r.team_id}
            for r in reqs]
    return Response(data)


# ── Respond to a supervision request ─────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_supervision_request(request, req_id):
    """POST /api/v1/teams/supervisor-requests/<req_id>/respond/  { action: accept|reject }"""
    req = get_object_or_404(SupervisionRequest, pk=req_id)
    if req.supervisor != request.user:
        return Response({'error': 'This request is not addressed to you.'}, status=403)
    if req.status != SupervisionRequest.STATUS_PENDING:
        return Response({'error': 'Request already decided.'}, status=400)
    action = request.data.get('action')
    if action not in ('accept', 'reject'):
        return Response({'error': "action must be 'accept' or 'reject'."}, status=400)
    if action == 'accept':
        req.status = SupervisionRequest.STATUS_ACCEPTED
        req.save()
        team = req.team
        team.assigned_supervisor = request.user
        team.save(update_fields=['assigned_supervisor'])
        for member in team.members.all():
            push_notification(
                recipient_id=member.pk,
                title='Supervisor accepted',
                message=f'Dr. {request.user.display_name} has accepted to supervise {team.name}.',
                notif_type='supervisor_assigned',
                team_name=team.name,
            )
    else:
        req.status = SupervisionRequest.STATUS_REJECTED
        req.save()
        push_notification(
            recipient_id=req.team.leader_id,
            title='Supervisor request rejected',
            message=f'Dr. {request.user.display_name} declined to supervise {req.team.name}.',
            notif_type='request_rejected',
            team_name=req.team.name,
        )
    return Response({'id': req.pk, 'status': req.status, 'priority': req.priority,
                     'supervisor': req.supervisor_id, 'team': req.team_id})
