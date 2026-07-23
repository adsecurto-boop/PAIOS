"""PAIOS Learning & Knowledge Engine (Milestone 8).

Observes completed History, extracts patterns, produces reusable
knowledge: Insights (from Reflections), Findings, Trends, Candidate
Principles, Candidate Habit Changes, and Learning/Trend/Period reports.

It never reasons about the future, never schedules, never transitions
entities, never modifies historical evidence, and never edits Principles
or Habits — it proposes; the Application (a later wiring) decides.
Deterministic expert analysis only: identical history yields identical
output, including generated identifiers. No AI, no ML, no randomness,
no clock.
"""

from paios.learning.analyzer import (
    Finding,
    FindingKind,
    Trend,
    TrendDirection,
    analyze_patterns,
    analyze_trends,
)
from paios.learning.exceptions import InvalidHistoryError, LearningError
from paios.learning.extractor import AnalysisWindow, Observations, extract
from paios.learning.habit_analyzer import (
    CandidateHabitChange,
    HabitChangeAction,
    propose_habit_changes,
)
from paios.learning.history import History, HistoryLoader
from paios.learning.learning_engine import (
    LearningEngine,
    LearningReport,
    LearningResult,
    PeriodSummary,
    TrendReport,
)
from paios.learning.principle_generator import (
    CandidatePrinciple,
    propose_principles,
)
from paios.learning.reflection_engine import (
    ReflectionQuality,
    analyze_reflections,
)

__all__ = [
    "AnalysisWindow",
    "CandidateHabitChange",
    "CandidatePrinciple",
    "Finding",
    "FindingKind",
    "HabitChangeAction",
    "History",
    "HistoryLoader",
    "InvalidHistoryError",
    "LearningEngine",
    "LearningError",
    "LearningReport",
    "LearningResult",
    "Observations",
    "PeriodSummary",
    "ReflectionQuality",
    "Trend",
    "TrendDirection",
    "TrendReport",
    "analyze_patterns",
    "analyze_reflections",
    "analyze_trends",
    "extract",
    "propose_habit_changes",
    "propose_principles",
]
