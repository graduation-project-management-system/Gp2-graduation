from django.db import models
from django.conf import settings


class SupervisorRequest(models.Model):
    """
    A team's ranked request to be supervised.
    Preferences are stored as an ordered list; if the target supervisor rejects,
    the system automatically advances to the next preference.
    """

    class ReqStatus(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'  # all preferences exhausted
        FORWARDED = 'forwarded', 'Forwarded'

    team          = models.ForeignKey(
        'teams.Team',
        related_name='supervisor_requests',
        on_delete=models.CASCADE,
    )
    project_idea  = models.CharField(max_length=500)
    leader        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='submitted_requests',
        on_delete=models.CASCADE,
    )
    # Ordered list of supervisor PKs, e.g. [3, 7, 12]
    preferences   = models.JSONField(default=list)
    current_index = models.PositiveSmallIntegerField(default=0)
    target_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='received_requests',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'supervisor'},
    )
    project_file  = models.FileField(upload_to='request_files/', null=True, blank=True)
    status        = models.CharField(max_length=20, choices=ReqStatus.choices, default=ReqStatus.PENDING)
    approved_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='approved_requests',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    decided_at    = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'requests_supervisorrequest'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.team.name} → {self.target_supervisor} [{self.status}]'
