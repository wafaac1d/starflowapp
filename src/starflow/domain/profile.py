from datetime import time

from starflow.domain.errors import BirthTimeInvalid


def ensure_birth_time(birth_time: time | None, unknown: bool) -> None:
    if unknown and birth_time is not None:
        raise BirthTimeInvalid("unknown birth time cannot include a clock time")
