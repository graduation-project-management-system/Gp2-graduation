from django.db import models
from django.conf import settings


class TeamStatus(models.TextChoices):
    FORMING  = 'forming',  'Forming'
    ACTIVE   = 'active',   'Active'
    COMPLETE = 'complete', 'Complete'
    DISBANDED = 'disbanded', 'Disbanded'


class Team(models.Model):
    """
    A graduation-project team (1–5 students + 1 supervisor).
    """
    name                = models.CharField(max_length=120, unique=True)
    project_title       = models.CharField(max_length=255)
    project_description = models.TextField(blank=True)
    status              = models.CharField(max_length=20, choices=TeamStatus.choices, default=TeamStatus.FORMING)
    leader              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='led_teams',
        on_delete=models.SET_NULL,
        null=True,
    )
    members             = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='member_teams',
        blank=True,
    )
    assigned_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='supervised_teams',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'supervisor'},
    )
    progress            = models.PositiveSmallIntegerField(default=0)   # 0-100
    academic_year       = models.CharField(max_length=10, default='2025-2026')
    is_archived         = models.BooleanField(default=False)
    archive_date        = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'teams_team'
        ordering  = ['-created_at']

    def __str__(self):
        return self.name


class ExamDate(models.Model):
    """Exam dates that block meeting scheduling for a team."""
    team = models.ForeignKey(Team, related_name='exam_dates', on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        db_table = 'teams_examdate'
        unique_together = ('team', 'date')

    def __str__(self):
        return f'{self.team.name} – {self.date}'


class MembershipRequest(models.Model):
    """Student requests to join a team. Approved by majority vote (>50%) of current members."""

    class ReqStatus(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    team      = models.ForeignKey(Team, related_name='membership_requests', on_delete=models.CASCADE)
    student   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='join_requests'
    )
    status    = models.CharField(max_length=20, choices=ReqStatus.choices, default=ReqStatus.PENDING)

    # Voters — tracked to prevent double-voting and to calculate majority
    yes_voters = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='voted_yes_requests', blank=True
    )
    no_voters  = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='voted_no_requests', blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'teams_membershiprequest'
        unique_together = ('team', 'student')


class SupervisionRequest(models.Model):
    """One supervision request per supervisor per team (max 3 per team)."""
    STATUS_PENDING  = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]

    team       = models.ForeignKey(Team, related_name='supervision_requests', on_delete=models.CASCADE)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='supervision_requests_received',
        on_delete=models.CASCADE, limit_choices_to={'role': 'supervisor'},
    )
    priority   = models.PositiveSmallIntegerField(default=1)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'teams_supervisionrequest'
        unique_together = ('team', 'supervisor')
        ordering        = ['priority']
