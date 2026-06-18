from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.teams.models import Team
from apps.accounts.models import UserRole
from apps.notifications.utils import push_notification
from .models import TeamFile
from .serializers import TeamFileSerializer


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_files(request):
    """
    GET  /api/v1/files/?team_id=<id>  — list files
    POST /api/v1/files/               — upload a file (multipart, fields: team_id, file)
    """
    user = request.user

    if request.method == 'POST':
        team_id = request.data.get('team_id') or request.POST.get('team_id')
        file    = request.FILES.get('file')
        if not team_id or not file:
            return Response({'error': 'team_id and file are required.'}, status=400)

        team = get_object_or_404(Team, pk=team_id)

        # Only team members or the assigned supervisor may upload
        is_member = team.members.filter(pk=user.pk).exists()
        is_sup    = team.assigned_supervisor_id == user.pk
        if not (is_member or is_sup or user.role == UserRole.ADMIN):
            return Response({'error': 'Not authorised to upload to this team.'}, status=403)

        tf = TeamFile.objects.create(team=team, uploader=user, file=file, file_name=file.name)

        # Notify supervisor when a student uploads a file
        if user.role == UserRole.STUDENT and team.assigned_supervisor:
            push_notification(
                recipient_id=team.assigned_supervisor.pk,
                title='New file uploaded',
                message=f'{user.display_name} uploaded "{file.name}" for team {team.name}.',
                notif_type='file_uploaded',
                team_name=team.name,
            )

        return Response(TeamFileSerializer(tf, context={'request': request}).data, status=201)

    # GET
    team_id = request.query_params.get('team_id')

    if user.role == UserRole.SUPERVISOR:
        qs = TeamFile.objects.filter(team__assigned_supervisor=user)
    elif user.role == UserRole.STUDENT:
        teams = Team.objects.filter(members=user)
        qs    = TeamFile.objects.filter(team__in=teams)
    else:
        qs = TeamFile.objects.all()

    if team_id:
        qs = qs.filter(team_id=team_id)

    return Response(TeamFileSerializer(qs, many=True, context={'request': request}).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request, pk):
    """DELETE /api/v1/files/<pk>/  — uploader or supervisor only."""
    team_file = get_object_or_404(TeamFile, pk=pk)
    team      = team_file.team

    if team_file.uploader != request.user and team.assigned_supervisor != request.user:
        return Response({'error': 'Not authorised to delete this file.'}, status=403)

    team_file.file.delete(save=False)
    team_file.delete()
    return Response({'detail': 'File deleted.'}, status=204)
