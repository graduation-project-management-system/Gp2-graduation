"""
Interface Serializers — two responsibilities:
  1. Output serializers: convert domain entities → JSON dicts.
  2. Input serializers: validate raw request data before passing to use cases.
"""
from rest_framework import serializers


# ── Output Serializers (Entity → JSON) ───────────────────────────────────────

class AvailabilitySlotOutputSerializer(serializers.Serializer):
    """Serializes AvailabilitySlotEntity."""

    def to_representation(self, entity):
        return {
            'id':         entity.id,
            'date':       str(entity.date),
            'start_time': entity.start_time.strftime('%H:%M'),
            'end_time':   entity.end_time.strftime('%H:%M'),
            'mode':       entity.mode.value,
            'is_open':    entity.is_open,
        }


class MeetingOutputSerializer(serializers.Serializer):
    """Serializes MeetingEntity."""

    def to_representation(self, entity):
        return {
            'id':           entity.id,
            'team_id':      entity.team_id,
            'team_name':    entity.team_name,
            'meeting_type': entity.meeting_type.value,
            'date':         str(entity.date),
            'time':         entity.time.strftime('%H:%M'),
            'topic':        entity.topic,
            'created_at':   str(entity.created_at) if entity.created_at else None,
        }


class GradingReportOutputSerializer(serializers.Serializer):
    """Serializes GradingReportEntity with all three raw scores + computed final."""

    def to_representation(self, entity):
        return {
            'id':                   entity.id,
            'team_id':              entity.team_id,
            'team_name':            entity.team_name,
            'phase':                entity.phase.value,
            'chief_grade':          entity.grade.chief_grade,
            'examiner_one_grade':   entity.grade.examiner_one_grade,
            'examiner_two_grade':   entity.grade.examiner_two_grade,
            'final_grade':          entity.final_grade,
            'feedback':             entity.feedback,
            'created_at':           str(entity.created_at) if entity.created_at else None,
        }


class SupervisorRequestOutputSerializer(serializers.Serializer):
    """Serializes SupervisorRequestEntity."""

    def to_representation(self, entity):
        return {
            'id':                   entity.id,
            'team_id':              entity.team_id,
            'team_name':            entity.team_name,
            'project_idea':         entity.project_idea,
            'leader_name':          entity.leader_name,
            'status':               entity.status.value,
            'preferences':          entity.preferences,
            'current_index':        entity.current_index,
            'target_supervisor_id': entity.target_supervisor_id,
            'created_at':           str(entity.created_at) if entity.created_at else None,
        }


class TeamFileOutputSerializer(serializers.Serializer):
    """Serializes TeamFileEntity. file_url is built by the view using request.build_absolute_uri."""

    def to_representation(self, entity):
        request = self.context.get('request')
        file_url = None
        if entity.file_path and request:
            from django.conf import settings as django_settings
            file_url = request.build_absolute_uri(
                django_settings.MEDIA_URL + entity.file_path
            )
        return {
            'id':            entity.id,
            'team_id':       entity.team_id,
            'team_name':     entity.team_name,
            'uploader_name': entity.uploader_name,
            'file_name':     entity.file_name,
            'description':   entity.description,
            'file_url':      file_url,
            'created_at':    str(entity.created_at) if entity.created_at else None,
        }


class NotificationOutputSerializer(serializers.Serializer):
    """Serializes NotificationEntity."""

    def to_representation(self, entity):
        return {
            'id':         entity.id,
            'title':      entity.title,
            'message':    entity.message,
            'notif_type': entity.notif_type,
            'team_name':  entity.team_name,
            'is_read':    entity.is_read,
            'created_at': str(entity.created_at) if entity.created_at else None,
        }


# ── Input Serializers (Request Data → Validated Values) ──────────────────────

class AddSlotInputSerializer(serializers.Serializer):
    date       = serializers.DateField()
    start_time = serializers.TimeField()
    end_time   = serializers.TimeField()
    mode       = serializers.ChoiceField(choices=['Direct', 'Online', 'Both'])

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError(
                {'end_time': 'end_time must be after start_time.'}
            )
        return data


class BookMeetingInputSerializer(serializers.Serializer):
    team_id      = serializers.IntegerField(min_value=1)
    meeting_type = serializers.ChoiceField(choices=['Direct', 'Online'])
    topic        = serializers.CharField(required=False, allow_blank=True, default='')


class GradingReportInputSerializer(serializers.Serializer):
    team_id            = serializers.IntegerField(min_value=1)
    phase              = serializers.ChoiceField(choices=['Proposal', 'Midterm', 'Final'])
    chief_grade        = serializers.FloatField(min_value=0, max_value=100)
    examiner_one_grade = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True, default=None)
    examiner_two_grade = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True, default=None)
    feedback           = serializers.CharField(required=False, allow_blank=True, default='')


class DecideRequestInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['approve', 'reject'])
