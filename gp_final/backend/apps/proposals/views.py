from apps.activity.models import ActivityLog
from apps.activity.services import log_activity
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse, QueryDict
from django.http.multipartparser import MultiPartParser, MultiPartParserError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from apps.teams.models import Team
from apps.accounts.models import User

from .models import Proposal


ALLOWED_PROPOSAL_EXTENSIONS = {'.pdf', '.doc', '.docx'}


def _proposal_to_dict(proposal, request=None):
    file_url = ''
    file_name = ''
    if proposal.file:
        file_name = proposal.file.name.split('/')[-1]
        raw_url = proposal.file.url
        file_url = request.build_absolute_uri(raw_url) if request else raw_url

    supervisor_dict = None
    if proposal.supervisor_id:
        supervisor_dict = {
            'id': proposal.supervisor_id,
            'name': proposal.supervisor.get_full_name() or proposal.supervisor.username,
        }

    return {
        'id': proposal.id,
        'team_id': proposal.team_id,
        'team_name': proposal.team.name,
        'title': proposal.title,
        'file_name': file_name,
        'file_url': file_url,
        'supervisor': supervisor_dict,
        'status': proposal.status,
        'submitted_at': proposal.submitted_at.isoformat() if proposal.submitted_at else None,
    }


def _parse_form_like_body(request):
    if request.method == 'POST':
        return request.POST, request.FILES, None
    content_type = request.META.get('CONTENT_TYPE', '')
    if 'multipart/form-data' in content_type:
        try:
            parser = MultiPartParser(request.META, request, request.upload_handlers, request.encoding)
            data, files = parser.parse()
            return data, files, None
        except MultiPartParserError:
            return None, None, JsonResponse(
                {'success': False, 'message': 'Invalid multipart form body.'},
                status=400,
            )
    try:
        data = QueryDict(request.body)
        return data, {}, None
    except Exception:
        return None, None, JsonResponse(
            {'success': False, 'message': 'Invalid request body.'},
            status=400,
        )


def _is_allowed_file(file_obj):
    if not isinstance(file_obj, UploadedFile):
        return False
    lower_name = file_obj.name.lower()
    return any(lower_name.endswith(ext) for ext in ALLOWED_PROPOSAL_EXTENSIONS)


def _normalize_proposal_status(value):
    lookup = {
        'pending': Proposal.Status.SUBMITTED,
        'submitted': Proposal.Status.SUBMITTED,
        'under_review': Proposal.Status.UNDER_REVIEW,
        'approved': Proposal.Status.ACCEPTED,
        'accepted': Proposal.Status.ACCEPTED,
        'rejected': Proposal.Status.REJECTED,
        'draft': Proposal.Status.DRAFT,
    }
    return lookup.get(str(value or '').strip().lower(), Proposal.Status.SUBMITTED)


def _sync_team_proposal_status(proposal):
    proposal.team.proposal_status = proposal.status
    proposal.team.save(update_fields=['proposal_status'])


def _sync_team_proposal_status_after_delete(team):
    latest = team.proposals.order_by('-submitted_at', '-pk').first()
    team.proposal_status = latest.status if latest else 'none'
    team.save(update_fields=['proposal_status'])


@csrf_exempt
def proposals_api(request):
    if request.method != 'GET':
        return JsonResponse(
            {'success': False, 'message': 'Method not allowed.'},
            status=405,
        )

    proposals = Proposal.objects.select_related('team', 'supervisor').all()
    data = [_proposal_to_dict(item, request=request) for item in proposals]
    return JsonResponse(
        {
            'success': True,
            'message': 'Proposals fetched successfully.',
            'count': len(data),
            'proposals': data,
        }
    )


@csrf_exempt
def create_proposal_api(request):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'Method not allowed.'},
            status=405,
        )

    payload = request.POST
    title = (payload.get('title') or '').strip()
    team_id = payload.get('team_id')
    supervisor_id = payload.get('supervisor_id')
    status = _normalize_proposal_status(payload.get('status'))
    file_obj = request.FILES.get('file')

    if not title:
        return JsonResponse({'success': False, 'message': 'Project title is required.'}, status=400)
    if not team_id:
        return JsonResponse({'success': False, 'message': 'Team is required.'}, status=400)
    if not supervisor_id:
        return JsonResponse({'success': False, 'message': 'Supervisor is required.'}, status=400)
    if not file_obj:
        return JsonResponse({'success': False, 'message': 'Proposal file is required.'}, status=400)
    if not _is_allowed_file(file_obj):
        return JsonResponse({'success': False, 'message': 'Only PDF, DOC, and DOCX files are allowed.'}, status=400)

    if team_id:
       try:
        team = Team.objects.get(pk=int(team_id))
       except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid team selected.'}, status=400)
    else:
          team = Team.objects.first()
    

    try:
        supervisor = User.objects.filter(role=User.Role.SUPERVISOR).first()
    except Exception:
        supervisor = None

    submitted_at = timezone.now() if status != Proposal.Status.DRAFT else None
    proposal = Proposal.objects.create(
        team=team,
        supervisor=supervisor,
        title=title,
        file=file_obj,
        status=status,
        submitted_at=submitted_at,
    )
    _sync_team_proposal_status(proposal)
    proposal = Proposal.objects.select_related('team', 'supervisor').get(pk=proposal.pk)
    log_activity(
        action='Proposal Created',
        description=f"Proposal '{proposal.title}' (ID {proposal.id}) for team '{proposal.team.name}'.",
        related_type=ActivityLog.RelatedType.PROPOSAL,
        related_id=proposal.id,
        created_by=request.user,
    )
    return JsonResponse(
        {
            'success': True,
            'message': 'Proposal created successfully.',
            'proposal': _proposal_to_dict(proposal, request=request),
        },
        status=201,
    )


@csrf_exempt
def proposal_detail_api(request, proposal_id):
    try:
        proposal = Proposal.objects.select_related('team', 'supervisor').get(pk=proposal_id)
    except Proposal.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Proposal not found.'}, status=404)

    if request.method == 'PUT':
        data, files, error_response = _parse_form_like_body(request)
        if error_response:
            return error_response

        title = (data.get('title') or proposal.title).strip()
        supervisor_id = data.get('supervisor_id')
        status = _normalize_proposal_status(data.get('status') or proposal.status)

        if not title:
            return JsonResponse({'success': False, 'message': 'Project title is required.'}, status=400)

        if supervisor_id not in (None, '', 'null'):
            try:
                proposal.supervisor = User.objects.get(pk=int(supervisor_id), role=User.Role.SUPERVISOR)
            except Exception:
                return JsonResponse({'success': False, 'message': 'Invalid supervisor selected.'}, status=400)

        replace_file = files.get('file')
        if replace_file:
            if not _is_allowed_file(replace_file):
                return JsonResponse({'success': False, 'message': 'Only PDF, DOC, and DOCX files are allowed.'}, status=400)
            proposal.file = replace_file

        proposal.title = title
        proposal.status = status
        if status == Proposal.Status.DRAFT:
            proposal.submitted_at = None
        elif proposal.submitted_at is None:
            proposal.submitted_at = timezone.now()

        proposal.save()
        _sync_team_proposal_status(proposal)
        proposal = Proposal.objects.select_related('team', 'supervisor').get(pk=proposal.pk)
        return JsonResponse(
            {
                'success': True,
                'message': 'Proposal updated successfully.',
                'proposal': _proposal_to_dict(proposal, request=request),
            }
        )

    if request.method == 'DELETE':
        team = proposal.team
        pid, ptitle = proposal.id, proposal.title
        proposal.delete()
        _sync_team_proposal_status_after_delete(team)
        log_activity(
            action='Proposal Deleted',
            description=f"Proposal '{ptitle}' (ID {pid}) was deleted.",
            related_type=ActivityLog.RelatedType.PROPOSAL,
            related_id=pid,
            created_by=request.user,
        )
        return JsonResponse({'success': True, 'message': 'Proposal deleted successfully.'})

    return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)


@csrf_exempt
def approve_proposal_api(request, proposal_id):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'Method not allowed.'},
            status=405,
        )

    try:
        proposal = Proposal.objects.select_related('team', 'supervisor').get(pk=proposal_id)
    except Proposal.DoesNotExist:
        return JsonResponse(
            {'success': False, 'message': 'Proposal not found.'},
            status=404,
        )

    proposal.status = Proposal.Status.ACCEPTED
    if proposal.submitted_at is None:
        proposal.submitted_at = timezone.now()
        proposal.save(update_fields=['status', 'submitted_at'])
    else:
        proposal.save(update_fields=['status'])
    _sync_team_proposal_status(proposal)
    log_activity(
        action='Proposal Approved',
        description=f"Proposal '{proposal.title}' (ID {proposal.id}) was approved.",
        related_type=ActivityLog.RelatedType.PROPOSAL,
        related_id=proposal.id,
        created_by=request.user,
    )
    return JsonResponse(
        {
            'success': True,
            'message': 'Proposal approved successfully.',
            'proposal': _proposal_to_dict(proposal, request=request),
        }
    )


@csrf_exempt
def reject_proposal_api(request, proposal_id):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'Method not allowed.'},
            status=405,
        )

    try:
        proposal = Proposal.objects.select_related('team', 'supervisor').get(pk=proposal_id)
    except Proposal.DoesNotExist:
        return JsonResponse(
            {'success': False, 'message': 'Proposal not found.'},
            status=404,
        )

    proposal.status = Proposal.Status.REJECTED
    if proposal.submitted_at is None:
        proposal.submitted_at = timezone.now()
        proposal.save(update_fields=['status', 'submitted_at'])
    else:
        proposal.save(update_fields=['status'])
    _sync_team_proposal_status(proposal)
    log_activity(
        action='Proposal Rejected',
        description=f"Proposal '{proposal.title}' (ID {proposal.id}) was rejected.",
        related_type=ActivityLog.RelatedType.PROPOSAL,
        related_id=proposal.id,
        created_by=request.user,
    )
    return JsonResponse(
        {
            'success': True,
            'message': 'Proposal rejected successfully.',
            'proposal': _proposal_to_dict(proposal, request=request),
        }
    )
