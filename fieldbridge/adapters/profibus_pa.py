from ..core.adapter import create_adapter
from .rules import check_range


def validate(frame):
    check_range(frame, "address", 0, 127, "station address")
    check_range(frame, "source_address", 0, 127, "source station address")


profibus_definition = {
    "max_payload": 244,
    "validate": validate,
    "fields": ["address", "source_address"],
    "uses_device_address": True,
}

profibus_pa_adapter = create_adapter({"protocol": "profibus-pa", **profibus_definition})
