import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.teams.models import Team
from apps.notifications.utils import push_notification
from .models import SupervisorRequest
from .serializers import (
    SupervisorRequestCreateSerializer,
    SupervisorRequestSerializer,
    DecideRequestSerializer,
)

User = get_user_model()
MAX_TEAMS = getattr(settings, 'MAX_TEAMS_PER_SUPERVISOR', 5)


# ── Create a supervisor request ───────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_request(request):
    """
    POST /api/v1/requests/
    Multipart/Form-Data Body: 
    - project_idea (text)
    - project_file (file, optional)
    - preferences (stringified json array, e.g. '[1, 2, 3]')
    - students_data (stringified json array, optional)
    """
    if request.user.role != 'student':
        return Response({'error': 'Only students can submit supervisor requests.'}, status=403)

    # 1. التقاط البيانات القادمة من الـ FormData بحكم تحولها لنصوص
    project_idea = request.data.get('project_idea', '')
    
    # التقاط الملف المرفوع من حقل project_file
    project_file = request.FILES.get('project_file', None)

    # فك تشفير المصفوفات القادمة كنص من المتصفح
    try:
        preferences_raw = request.data.get('preferences', '[]')
        preferences = json.loads(preferences_raw) if isinstance(preferences_raw, str) else preferences_raw
    except Exception:
        return Response({'error': 'Invalid format for preferences list.'}, status=400)

    if not isinstance(preferences, list) or not preferences:
        return Response({'error': 'Preferences list is required and must be an array.'}, status=400)

    # 2. جلب فريق الطالب الحالي (البحث عن الفريق الذي يقوده هذا الطالب)
    team = Team.objects.filter(leader=request.user).first()
    if not team:
        return Response({'error': 'Only the team leader can submit a request, or team not found.'}, status=403)

    # التأكد من عدم وجود طلبات موافق عليها مسبقاً للفريق
    if SupervisorRequest.objects.filter(team=team, status='approved').exists():
        return Response({'error': 'This team already has an officially approved supervisor.'}, status=400)

    # 3. التحقق من صحة معرفات الدكاترة المختارين
    supervisors = User.objects.filter(pk__in=preferences, role='supervisor')
    found_ids = list(supervisors.values_list('pk', flat=True))
    ordered_ids = [pid for pid in preferences if int(pid) in found_ids]
    
    if not ordered_ids:
        return Response({'error': 'No valid supervisors found in your preferences.'}, status=400)

    # 4. تحديد أول دكتور في القائمة لإرسال الطلب له
    first_sup = User.objects.get(pk=ordered_ids[0])

    # 5. إنشاء سجل الطلب وحفظ الملف بداخل النموذج (Model) الخاص بكِ
    # ملاحظة: تأكدي أن موديل SupervisorRequest يحتوي على حقل للملف مثل (project_file = models.FileField...)
    req = SupervisorRequest.objects.create(
        team=team,
        project_idea=project_idea,
        leader=request.user,
        preferences=ordered_ids,
        current_index=0,
        target_supervisor=first_sup,
        status='pending',
        project_file=project_file if project_file else None,
    )

    # 6. إذا كنتِ ترغبين بتحديث بيانات الطلاب بالفريق فوراً بناءً على الحقل الممرر
    students_data_raw = request.data.get('students_data', None)
    if students_data_raw:
        try:
            students_data = json.loads(students_data_raw) if isinstance(students_data_raw, str) else students_data_raw
            # هنا يمكنكِ كتابة منطق لتحديث الـ GPA أو السجلات للطلاب بالفريق إذا لزم الأمر
        except Exception:
            pass

    # 7. إرسال الإشعار الفوري للدكتور الأول
    push_notification(
        recipient_id=first_sup.pk,
        title='New team request',
        message=f'{team.name} requested you as supervisor for "{project_idea}".',
        notif_type='supervisor_request',
        team_name=team.name,
    )

    return Response(SupervisorRequestSerializer(req, context={'request': request}).data, status=201)

# ── List requests for the current user ───────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_requests(request):
    """
    GET /api/v1/requests/
    • Supervisor  → pending requests targeting them
    • Student     → all requests for their team
    • Admin       → all requests
    """
    user = request.user
    if user.role == 'supervisor':
        qs = SupervisorRequest.objects.filter(target_supervisor=user, status='pending')
    elif user.role == 'student':
        teams = Team.objects.filter(members=user)
        qs    = SupervisorRequest.objects.filter(team__in=teams)
    else:
        qs = SupervisorRequest.objects.all()

    return Response(SupervisorRequestSerializer(qs, many=True, context={'request': request}).data)


# ── Decide (approve / reject) ─────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decide_request(request, pk):
    """
    POST /api/v1/requests/<pk>/decide/
    Body: { decision: 'approve' | 'reject' }
    Only the currently targeted supervisor may decide.
    """
    if request.user.role != 'supervisor':
        return Response({'error': 'Only supervisors can decide on requests.'}, status=403)

    req = get_object_or_404(SupervisorRequest, pk=pk)
    if req.target_supervisor != request.user or req.status != 'pending':
        return Response({'error': 'This request is not pending for you.'}, status=400)

    serializer = DecideRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    decision = serializer.validated_data['decision']

    if decision == 'approve':
        # Check supervisor capacity
        current_count = Team.objects.filter(assigned_supervisor=request.user).count()
        if current_count >= MAX_TEAMS:
            return Response(
                {'error': f'You have reached the maximum of {MAX_TEAMS} teams.'},
                status=400,
            )

        req.status      = 'approved'
        req.approved_by = request.user
        req.decided_at  = timezone.now()
        req.save()

        # Assign team
        team = req.team
        team.assigned_supervisor = request.user
        team.status = 'active'
        team.save()

        # Notify all team members
        for member in team.members.all():
            push_notification(
                recipient_id=member.pk,
                title='Supervisor assigned',
                message=f'Dr. {request.user.display_name} has accepted to supervise {team.name}.',
                notif_type='supervisor_assigned',
                team_name=team.name,
            )

    else:
        # Reject → forward to next preference
        next_index = req.current_index + 1
        if next_index < len(req.preferences):
            next_sup_id = req.preferences[next_index]
            next_sup    = User.objects.filter(pk=next_sup_id, role='supervisor').first()
            if next_sup:
                req.current_index     = next_index
                req.target_supervisor = next_sup
                req.status            = 'pending'
                req.decided_at        = timezone.now()
                req.save()

                push_notification(
                    recipient_id=next_sup.pk,
                    title='New team request',
                    message=f'{req.team.name} requests you as supervisor (forwarded).',
                    notif_type='supervisor_request',
                    team_name=req.team.name,
                )
                return Response({'detail': 'Request forwarded to next supervisor.'})

        # All preferences exhausted
        req.status     = 'rejected'
        req.decided_at = timezone.now()
        req.save()

        push_notification(
            recipient_id=req.leader_id,
            title='Supervisor request rejected',
            message='All selected supervisors declined your request. Please submit a new one.',
            notif_type='request_rejected',
            team_name=req.team.name,
        )

    return Response(SupervisorRequestSerializer(req).data)
