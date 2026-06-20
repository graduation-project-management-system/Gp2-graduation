from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F

from apps.teams.models import Team


class Grade(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='grades',
    )
    supervisor_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Supervisor grade (0-100)'
    )
    committee1_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Committee Doctor 1 grade (0-100)'
    )
    committee2_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Committee Doctor 2 grade (0-100)'
    )
    final_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        help_text='Final grade (auto-calculated)'
    )
    letter_grade = models.CharField(
        max_length=2,
        blank=True,
        editable=False,
        help_text='Letter grade (auto-calculated)'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_grades',
    )

    class Meta:
        app_label = 'apps.grades'
        ordering = ['-created_at', '-pk']

    def __str__(self) -> str:
        return f'Grade for {self.team.name} - {self.final_grade or "Pending"}'

    def clean(self) -> None:
        super().clean()
        
        # Validate supervisor grade
        if self.supervisor_grade is not None:
            if self.supervisor_grade < 0 or self.supervisor_grade > 100:
                raise ValidationError({
                    'supervisor_grade': 'Supervisor grade must be between 0 and 100.'
                })
        
        # Validate committee grades
        if self.committee1_grade is not None:
            if self.committee1_grade < 0 or self.committee1_grade > 100:
                raise ValidationError({
                    'committee1_grade': 'Committee Doctor 1 grade must be between 0 and 100.'
                })
        
        if self.committee2_grade is not None:
            if self.committee2_grade < 0 or self.committee2_grade > 100:
                raise ValidationError({
                    'committee2_grade': 'Committee Doctor 2 grade must be between 0 and 100.'
                })

    def save(self, *args, **kwargs):
        # Only calculate grades if not using update_fields or if grade fields are being updated
        update_fields = kwargs.get('update_fields')
        if not update_fields or any(field in update_fields for field in ['supervisor_grade', 'committee1_grade', 'committee2_grade']):
            self.calculate_final_grade()
            self.calculate_letter_grade()
        super().save(*args, **kwargs)

    def calculate_final_grade(self) -> None:
        """Calculate final grade: (Supervisor Grade * 0.5) + (Committee1 Grade * 0.25) + (Committee2 Grade * 0.25)"""
        if (self.supervisor_grade is not None and 
            self.committee1_grade is not None and 
            self.committee2_grade is not None):
            self.final_grade = (self.supervisor_grade * 0.5) + (self.committee1_grade * 0.25) + (self.committee2_grade * 0.25)
        else:
            self.final_grade = None
    def calculate_letter_grade(self) -> None:
        """Generate detailed letter grade based on final grade"""
        if self.final_grade is None:
            self.letter_grade = ''
            return
        
        final = float(self.final_grade)
        if final >= 95:
            self.letter_grade = 'A+'
        elif final >= 85:
            self.letter_grade = 'A'
        elif final >= 80:
            self.letter_grade = 'A-'
        elif final >= 77:
            self.letter_grade = 'B+'
        elif final >= 73:
            self.letter_grade = 'B'
        elif final >= 70:
            self.letter_grade = 'B-'
        elif final >= 67:
            self.letter_grade = 'C+'
        elif final >= 63:
            self.letter_grade = 'C'
        elif final >= 60:
            self.letter_grade = 'C-'
        elif final >= 57:
            self.letter_grade = 'D+'
        elif final >= 50:
            self.letter_grade = 'D'
        else:
            self.letter_grade = 'F'
