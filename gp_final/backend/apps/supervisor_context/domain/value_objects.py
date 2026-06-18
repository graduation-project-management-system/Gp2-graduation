"""
Domain Value Objects — immutable, equality-by-value, self-validating.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import datetime


# ── Enumerations ──────────────────────────────────────────────────────────────

class MeetingType(str, Enum):
    DIRECT = 'Direct'
    ONLINE = 'Online'


class SlotMode(str, Enum):
    DIRECT = 'Direct'
    ONLINE = 'Online'
    BOTH   = 'Both'


class TeamStatus(str, Enum):
    ACTIVE    = 'active'
    DISBANDED = 'disbanded'


class RequestStatus(str, Enum):
    PENDING   = 'pending'
    APPROVED  = 'approved'
    REJECTED  = 'rejected'
    FORWARDED = 'forwarded'


class GradingPhase(str, Enum):
    PROPOSAL = 'Proposal'
    MIDTERM  = 'Midterm'
    FINAL    = 'Final'


# ── Value Objects ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MeetingSlot:
    """Represents a specific date+time for a meeting."""
    date: datetime.date
    time: datetime.time

    def __post_init__(self):
        if not isinstance(self.date, datetime.date):
            raise ValueError("date must be a datetime.date instance.")
        if not isinstance(self.time, datetime.time):
            raise ValueError("time must be a datetime.time instance.")


@dataclass(frozen=True)
class WeightedGrade:
    """
    Encapsulates the three grading scores and computes the weighted final grade.
    Weights: chief_supervisor 50%, examiner_one 25%, examiner_two 25%.
    Examiner grades are optional (None until submitted).
    """
    chief_grade:        float
    examiner_one_grade: Optional[float]
    examiner_two_grade: Optional[float]

    def __post_init__(self):
        if not (0.0 <= self.chief_grade <= 100.0):
            raise ValueError(f"chief_grade must be between 0 and 100, got {self.chief_grade}.")
        for name, score in [
            ('examiner_one_grade', self.examiner_one_grade),
            ('examiner_two_grade', self.examiner_two_grade),
        ]:
            if score is not None and not (0.0 <= score <= 100.0):
                raise ValueError(f"{name} must be between 0 and 100, got {score}.")

    @property
    def final_grade(self) -> Optional[float]:
        if self.examiner_one_grade is None or self.examiner_two_grade is None:
            return None
        return round(
            self.chief_grade        * 0.50 +
            self.examiner_one_grade * 0.25 +
            self.examiner_two_grade * 0.25,
            2,
        )
