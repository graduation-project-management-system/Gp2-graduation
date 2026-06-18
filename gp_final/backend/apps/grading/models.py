from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class GradingReport(models.Model):
    """
    Weighted final grade: chief_supervisor 50%, examiner_one 25%, examiner_two 25%.
    """

    class Phase(models.TextChoices):
        PROPOSAL = 'Proposal', 'Proposal'
        MIDTERM  = 'Midterm',  'Midterm'
        FINAL    = 'Final',    'Final'

    team               = models.ForeignKey(
        'teams.Team', related_name='grading_reports', on_delete=models.CASCADE
    )
    supervisor         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='grading_reports',
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'role': 'supervisor'},
    )
    phase              = models.CharField(max_length=20, choices=Phase.choices)

    # Raw scores (0-100)
    chief_grade        = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    examiner_one_grade = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
    )
    examiner_two_grade = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
    )

    # Computed (stored for fast lookup); null until all three grades are in
    final_grade        = models.DecimalField(max_digits=5, decimal_places=2, editable=False, null=True, blank=True)

    feedback           = models.TextField(blank=True)
    archived_file      = models.FileField(upload_to='grading_archives/', null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'grading_gradingreport'
        ordering = ['-created_at']
        # One report per team per phase
        unique_together = ('team', 'phase')

    def save(self, *args, **kwargs):
        if self.examiner_one_grade is not None and self.examiner_two_grade is not None:
            weights = getattr(settings, 'GRADING_WEIGHTS', {
                'chief_supervisor': 0.50,
                'examiner_one':     0.25,
                'examiner_two':     0.25,
            })
            self.final_grade = (
                float(self.chief_grade)        * weights['chief_supervisor'] +
                float(self.examiner_one_grade) * weights['examiner_one'] +
                float(self.examiner_two_grade) * weights['examiner_two']
            )
        else:
            self.final_grade = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.team.name} | {self.phase} | {self.final_grade}'
