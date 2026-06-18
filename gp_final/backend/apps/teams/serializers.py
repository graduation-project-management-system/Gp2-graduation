from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import UserRole
from .models import Team, ExamDate, MembershipRequest, TeamStatus

User = get_user_model()


class ExamDateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExamDate
        fields = ['id', 'date']


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'display_name', 'email', 'role']


class TeamSerializer(serializers.ModelSerializer):
    leader              = MemberSerializer(read_only=True)
    members             = MemberSerializer(many=True, read_only=True)
    members_info        = MemberSerializer(source='members', many=True, read_only=True)
    assigned_supervisor = MemberSerializer(read_only=True)
    exam_dates          = ExamDateSerializer(many=True, read_only=True)
    supervisor          = serializers.SerializerMethodField()
    members_count       = serializers.SerializerMethodField()

    def get_supervisor(self, obj):
        return obj.assigned_supervisor_id  # returns int or None

    def get_members_count(self, obj):
        return obj.members.count()

    class Meta:
        model  = Team
        fields = [
            'id', 'name', 'project_title', 'project_description',
            'status', 'leader', 'members', 'members_info', 'assigned_supervisor',
            'supervisor', 'members_count',
            'progress', 'academic_year', 'exam_dates',
            'is_archived', 'archive_date',
            'created_at', 'updated_at',
        ]


class TeamCreateSerializer(serializers.ModelSerializer):
    project_title       = serializers.CharField(required=False, allow_blank=True, default='')
    project_description = serializers.CharField(required=False, allow_blank=True, default='')
    status              = serializers.ChoiceField(
        choices=TeamStatus.choices,
        required=False,
        default='forming'
    )
    member_ids          = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model  = Team
        fields = ['name', 'project_title', 'project_description', 'academic_year', 'status', 'member_ids']

    def validate_name(self, value):
        """Check for duplicate team names."""
        if Team.objects.filter(name=value).exists():
            raise serializers.ValidationError('A team with this name already exists.')
        return value

    def validate_member_ids(self, value):
        """Validate member_ids: max 5, no duplicates, all students."""
        if not value:
            return value

        # Check max 5 members
        if len(value) > 5:
            raise serializers.ValidationError('Maximum 5 members allowed.')

        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate member IDs.')

        # Check all exist and are students
        User = get_user_model()
        members = User.objects.filter(pk__in=value)
        if members.count() != len(value):
            raise serializers.ValidationError('One or more member IDs do not exist.')

        for member in members:
            if member.role != UserRole.STUDENT:
                raise serializers.ValidationError(f'User {member.id} is not a student.')

        # NEW: Check that no member is already in any team
        for member in members:
            existing_team = Team.objects.filter(members=member).first()
            if existing_team:
                raise serializers.ValidationError(
                    f'Student {member.display_name} is already a member of team "{existing_team.name}".'
                )

        return value

    def create(self, validated_data):
        user = self.context['request'].user

        # Extract member_ids before creating
        member_ids = validated_data.pop('member_ids', None)

        # Default project_title to name if not provided
        if not validated_data.get('project_title'):
            validated_data['project_title'] = validated_data.get('name', '')

        # Determine leader
        if user.role == UserRole.ADMIN:
            # Admin case: member_ids required, first student becomes leader
            if not member_ids:
                raise serializers.ValidationError({'member_ids': 'Admin must select at least one student.'})
            User = get_user_model()
            leader = User.objects.get(pk=member_ids[0])
            validated_data['leader'] = leader
        else:
            # Student case: user is leader
            validated_data['leader'] = user

        # Create team
        team = Team.objects.create(**validated_data)

        # Add members
        if member_ids:
            team.members.set(member_ids)
        elif user.role == UserRole.STUDENT:
            # Student creating team adds themselves
            team.members.add(user)

        return team


class TeamUpdateSerializer(serializers.ModelSerializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model  = Team
        fields = ['project_title', 'project_description', 'status', 'progress', 'academic_year', 'member_ids']
        extra_kwargs = {f: {'required': False} for f in fields}

    def validate_member_ids(self, value):
        if value is None:
            return value

        if len(value) > 5:
            raise serializers.ValidationError('Maximum 5 members allowed.')

        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate member IDs.')

        User = get_user_model()
        members = User.objects.filter(pk__in=value)
        if members.count() != len(value):
            raise serializers.ValidationError('One or more member IDs do not exist.')

        for member in members:
            if member.role != UserRole.STUDENT:
                raise serializers.ValidationError(f'User {member.id} is not a student.')

        # NEW: Check that no member is already in a different team
        current_team_id = self.instance.pk if self.instance else None
        for member in members:
            other_team = Team.objects.filter(members=member).exclude(pk=current_team_id).first()
            if other_team:
                raise serializers.ValidationError(
                    f'Student {member.display_name} is already a member of team "{other_team.name}".'
                )

        return value

    def update(self, instance, validated_data):
        member_ids = validated_data.pop('member_ids', None)
        team = super().update(instance, validated_data)
        if member_ids is not None:
            team.members.set(member_ids)
        return team


class ExamDateAddSerializer(serializers.Serializer):
    date = serializers.DateField()


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'email']

class MembershipRequestSerializer(serializers.ModelSerializer):
    student_info   = MemberSerializer(source='student', read_only=True)
    yes_count      = serializers.SerializerMethodField()
    no_count       = serializers.SerializerMethodField()
    my_vote        = serializers.SerializerMethodField()
    required_votes = serializers.SerializerMethodField()
    total_members  = serializers.SerializerMethodField()

    def get_yes_count(self, obj):
        return obj.yes_voters.count()

    def get_no_count(self, obj):
        return obj.no_voters.count()

    def get_my_vote(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if obj.yes_voters.filter(pk=request.user.pk).exists():
            return 'yes'
        if obj.no_voters.filter(pk=request.user.pk).exists():
            return 'no'
        return None

    def get_required_votes(self, obj):
        total = obj.team.members.count()
        return max(1, total // 2 + 1)   # strict majority

    def get_total_members(self, obj):
        return obj.team.members.count()

    class Meta:
        model  = MembershipRequest
        fields = [
            'id', 'team', 'student', 'student_info', 'status', 'created_at',
            'yes_count', 'no_count', 'my_vote', 'required_votes', 'total_members',
        ]
