from typing import Callable, TypeVar

from .errors import FieldbridgeError, is_fieldbridge_error
from ..core.types import AttrDict

T = TypeVar("T")


def to_result(fn: Callable[[], T]) -> AttrDict:
    try:
        return AttrDict(ok=True, value=fn())
    except FieldbridgeError as error:
        return AttrDict(ok=False, error=error)
    except Exception as error:
        wrapped = FieldbridgeError("INTERNAL", str(error), cause=error)
        return AttrDict(ok=False, error=wrapped)


toResult = to_result
