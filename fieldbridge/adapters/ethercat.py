from ..core.adapter import create_adapter
from .rules import check_range


def validate(frame):
    check_range(frame, "address", 0, 0xffff, "station address")


ethercat_adapter = create_adapter({
    "protocol": "ethercat",
    "max_payload": 1486,
    "validate": validate,
    "fields": ["address"],
    "uses_device_address": True,
})
