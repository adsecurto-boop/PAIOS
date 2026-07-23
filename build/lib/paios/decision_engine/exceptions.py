"""Decision Engine exceptions."""


class DecisionEngineError(Exception):
    """Base class for every Decision Engine error."""


class InvalidSnapshotError(DecisionEngineError):
    """The RuntimeSnapshot is incoherent for reasoning purposes
    (DECISION_ENGINE.md section 3, "Validate Runtime State"). Invalid state
    produces invalid reasoning, so the engine refuses instead of guessing."""
