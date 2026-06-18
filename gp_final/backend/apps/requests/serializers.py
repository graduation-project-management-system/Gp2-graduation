from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SupervisorRequest

User = get_user_model()


class SupervisorRequestCreateSerializer(serializers.Serializer):
    team_id      = serializers.IntegerField()
    project_idea = serializers.CharField(max_length=500)
    preferences  = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=5,
    )


class SupervisorRequestSerializer(serializers.ModelSerializer):
    team_name              = serializers.CharField(source='team.name', read_only=True)
    project_title          = serializers.CharField(source='team.project_title', read_only=True)
    project_description    = serializers.CharField(source='team.project_description', read_only=True)
    leader_name            = serializers.CharField(source='leader.display_name', read_only=True)
    target_supervisor_name = serializers.CharField(
        source='target_supervisor.display_name', read_only=True, default=None
    )
    members                = serializers.SerializerMethodField()
    file_url               = serializers.SerializerMethodField()

    def get_members(self, obj):
        if not obj.team:
            return []
        return [
            {
                'name': m.display_name,
                'email': m.email,
                'gpa': float(m.gpa) if m.gpa is not None else None,
            }
            for m in obj.team.members.all()
        ]

    def get_file_url(self, obj):
        if not obj.project_file:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.project_file.url)
        return obj.project_file.url

    class Meta:
        model  = SupervisorRequest
        fields = [
            'id', 'team_name', 'project_title', 'project_description',
            'leader_name', 'project_idea', 'members', 'file_url',
            'preferences', 'current_index',
            'target_supervisor_name', 'status',
            'decided_at', 'created_at',
        ]


class DecideRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['approve', 'reject'])
