from django.db import models
from django.conf import settings


class AvailabilitySlot(models.Model):
    """A time window a supervisor is available for meetings."""

    class SlotMode(models.TextChoices):
        DIRECT = 'Direct', 'Direct'
        ONLINE = 'Online', 'Online'
        BOTH   = 'Both',   'Both'

    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='availability_slots',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'supervisor'},
    )
    date       = models.DateField()
    start_time = models.TimeField()
    end_time   = models.TimeField()
    mode       = models.CharField(max_length=10, choices=SlotMode.choices, default=SlotMode.BOTH)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'meetings_availabilityslot'
        ordering = ['date', 'start_time']

    def __str__(self):
        return f'{self.supervisor.display_name} | {self.date} {self.start_time}-{self.end_time} ({self.mode})'

    @property
    def is_open(self):
        from django.utils import timezone
        import datetime
        slot_end = timezone.make_aware(
            datetime.datetime.combine(self.date, self.end_time)
        )
        return slot_end >= timezone.now()


class Meeting(models.Model):
    """A booked meeting between a supervisor and a team."""

    class MeetingType(models.TextChoices):
        DIRECT = 'Direct', 'Direct'
        ONLINE = 'Online', 'Online'

    supervisor   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='meetings_as_supervisor',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'supervisor'},
    )
    examiner1    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='meetings_as_examiner1',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'supervisor'},
    )
    examiner2    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='meetings_as_examiner2',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'supervisor'},
    )
    team         = models.ForeignKey(
        'teams.Team',
        related_name='meetings',
        on_delete=models.CASCADE,
    )
    date         = models.DateField()
    time         = models.TimeField()
    meeting_type = models.CharField(max_length=10, choices=MeetingType.choices, default=MeetingType.ONLINE)
    topic        = models.CharField(max_length=500, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'meetings_meeting'
        ordering        = ['date', 'time']
        unique_together = ('supervisor', 'date', 'time')   # no double-booking

    def __str__(self):
        return f'{self.supervisor.display_name} ↔ {self.team.name} on {self.date} {self.time}'
