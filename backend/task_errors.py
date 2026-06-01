# STIGMER AI — stigmergy task API error codes (machine-readable 409 bodies).


class TaskConflictError(Exception):
    """Base for expected task conflicts (HTTP 409, not retry loops)."""

    error: str

    def __init__(self, error: str, message: str = "") -> None:
        self.error = error
        super().__init__(message or error)


class AlreadyClaimedError(TaskConflictError):
    def __init__(self) -> None:
        super().__init__("already_claimed", "Task already claimed")


class LeaseLostError(TaskConflictError):
    def __init__(self) -> None:
        super().__init__("lease_lost", "Lease lost")


class NotTaskHolderError(TaskConflictError):
    def __init__(self) -> None:
        super().__init__("not_holder", "Not task holder")


class VersionConflictError(TaskConflictError):
    def __init__(self, card_id: str, expected_version: int) -> None:
        super().__init__(
            "version_conflict",
            f"Version conflict for card {card_id}: expected {expected_version}",
        )
