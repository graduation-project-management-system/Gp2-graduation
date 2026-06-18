import json
from datetime import date, time

from apps.activity.models import ActivityLog
from apps.activity.services import log_activity
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.teams.models import Team

from .models import DefenseSchedule


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}'), None
    except json.JSONDecodeError:
        return None, JsonResponse(
            {'success': False, 'message': 'Invalid JSON body.'},
            status=400,
        )


def _defense_to_dict(defense):
    return {
        'id': defense.id,
        'team_id': defense.team_id,
        'team_name': defense.team.name,
        'date': defense.date.isoformat(),
        'time': defense.time.isoformat(timespec='minutes'),
        'location': defense.location,
        'created_at': defense.created_at.isoformat() if defense.created_at else None,
    }


@csrf_exempt
def defense_api(request):
    if request.method == 'GET':
        schedules = DefenseSchedule.objects.select_related('team').all()
        data = [_defense_to_dict(item) for item in schedules]
        return JsonResponse(
            {
                'success': True,
                'message': 'Defense schedules fetched successfully.',
                'count': len(data),
                'defenses': data,
            }
        )

    if request.method == 'POST':
        return create_defense_api(request)

    return JsonResponse(
        {'success': False, 'message': 'Method not allowed.'},
        status=405,
    )


@csrf_exempt
def create_defense_api(request):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'Method not allowed.'},
            status=405,
        )

    payload, error_response = _parse_json_body(request)
    if error_response:
        return error_response

    schedule_type = payload.get('schedule_type', 'defense')

    team_id = payload.get('team_id')
    scheduled_date = payload.get('date')
    scheduled_time = payload.get('time')
    location = (payload.get('location') or '').strip()

    task_title = (payload.get('task_title') or '').strip()
    task_description = (payload.get('task_description') or '').strip()
    task_deadline = payload.get('task_deadline')

    if schedule_type == 'defense':
     if not team_id or not scheduled_date or not scheduled_time:
        return JsonResponse(
            {'success': False, 'message': 'team_id, date and time are required.'},
            status=400,
        )

    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return JsonResponse(
            {'success': False, 'message': 'Team not found.'},
            status=404,
        )

    try:
        defense_date = date.fromisoformat(scheduled_date)
        defense_time = time.fromisoformat(scheduled_time)
    except ValueError:
        return JsonResponse(
            {'success': False, 'message': 'date/time must be ISO format (YYYY-MM-DD, HH:MM[:SS]).'},
            status=400,
        )

    defense = DefenseSchedule.objects.create(
        team=team,
        date=defense_date,
        time=defense_time,
        location=location,
    )
    log_activity(
        action='Defense Scheduled',
        description=f"Defense for team '{team.name}' (ID {team.id}) on {defense_date} at {defense_time} — {location}.",
        related_type=ActivityLog.RelatedType.DEFENSE,
        related_id=defense.id,
        created_by=request.user,
    )

    return JsonResponse(
        {
            'success': True,
            'message': 'Created successfully',
            'data': _defense_to_dict(defense),
        },
        status=201,
    )
