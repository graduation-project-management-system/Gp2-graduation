"""
Domain Entities — have identity (id), mutable state, and encapsulate business rules.
"""
from dataclasses import dataclass, field
from typing import List, Optional
import datetime

from .value_objects import (
    MeetingType, SlotMode, TeamStatus,
    RequestStatus, GradingPhase, WeightedGrade,
)


@dataclass
class SupervisorEntity:
    id:           int
    email:        str
    display_name: str
    department:   str
    expertise:    str

    def __eq__(self, other):
        return isinstance(other, SupervisorEntity) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class TeamEntity:
    id:                     int
    name:                   str
    status:                 TeamStatus
    leader_id:              int
    member_ids:             List[int] = field(default_factory=list)
    assigned_supervisor_id: Optional[int] = None

    def is_full(self) -> bool:
        """A team may not exceed 5 members."""
        return len(self.member_ids) >= 5

    def is_active(self) -> bool:
        return self.status == TeamStatus.ACTIVE

    def has_supervisor(self) -> bool:
        return self.assigned_supervisor_id is not None

    def __eq__(self, other):
        return isinstance(other, TeamEntity) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class AvailabilitySlotEntity:
    id:            int
    supervisor_id: int
    date:          datetime.date
    start_time:    datetime.time
    end_time:      datetime.time
    mode:          SlotMode

    def duration_minutes(self) -> int:
        start = self.start_time.hour * 60 + self.start_time.minute
        end   = self.end_time.hour   * 60 + self.end_time.minute
        return end - start

    @property
    def is_open(self) -> bool:
        """True if the slot end time is in the future."""
        from django.utils import timezone
        slot_end = timezone.make_aware(
            datetime.datetime.combine(self.date, self.end_time)
        )
        return slot_end >= timezone.now()


@dataclass
class MeetingEntity:
    id:           int
    supervisor_id: int
    team_id:      int
    team_name:    str
    meeting_type: MeetingType
    date:         datetime.date
    time:         datetime.time
    topic:        str
    created_at:   Optional[datetime.datetime] = None


@dataclass
class GradingReportEntity:
    id:            Optional[int]
    supervisor_id: int
    team_id:       int
    team_name:     str
    phase:         GradingPhase
    grade:         WeightedGrade     # Value Object — encapsulates all three scores
    feedback:      str
    created_at:    Optional[datetime.datetime] = None

    @property
    def final_grade(self) -> Optional[float]:
        return self.grade.final_grade


@dataclass
class SupervisorRequestEntity:
    id:                   int
    team_id:              int
    team_name:            str
    project_idea:         str
    leader_id:            int
    leader_name:          str
    preferences:          List[int]     # ordered list of supervisor PKs
    current_index:        int
    target_supervisor_id: Optional[int]
    status:               RequestStatus
    created_at:           Optional[datetime.datetime] = None

    def next_supervisor_id(self) -> Optional[int]:
        next_idx = self.current_index + 1
        if next_idx < len(self.preferences):
            return self.preferences[next_idx]
        return None

    def all_preferences_exhausted(self) -> bool:
        return (self.current_index + 1) >= len(self.preferences)


@dataclass
class TeamFileEntity:
    id:            Optional[int]
    team_id:       int
    team_name:     str
    uploader_id:   int
    uploader_name: str
    file_name:     str
    description:   str
    file_path:     str               # relative path for building URL
    created_at:    Optional[datetime.datetime] = None


@dataclass
class NotificationEntity:
    id:         int
    recipient_id: int
    title:      str
    message:    str
    notif_type: str
    team_name:  str
    is_read:    bool
    created_at: Optional[datetime.datetime] = None
