from ..core.errors import FieldbridgeError


def check_range(frame, field, minimum, maximum, label=None):
    value = frame.get(field)
    if value is not None and (value < minimum or value > maximum):
        label = label or field
        raise FieldbridgeError("INVALID_FIELD",
                               f"{frame['protocol']} {label} must be {minimum}..{maximum}",
                               protocol=frame["protocol"], field=field)


def require_field(frame, field, hint):
    if frame.get(field) is None:
        raise FieldbridgeError("MISSING_FIELD",
                               f"{frame['protocol']} requires {hint}",
                               protocol=frame["protocol"], field=field)


def payload_error(frame, message):
    return FieldbridgeError("INVALID_PAYLOAD", message,
                            protocol=frame["protocol"], field="payload")
