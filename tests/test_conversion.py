import pytest

from fieldbridge import (
    FieldbridgeError,
    adapters,
    convert_frame,
    convert_message,
    create_adapter,
    create_converter,
    try_convert_frame,
    validate_frame,
)


def error_code(fn):
    try:
        fn()
    except FieldbridgeError as error:
        return error.code
    raise AssertionError("expected FieldbridgeError")


def test_conversion_and_payload_preservation():
    result = convert_frame({
        "source": {"protocol": "can", "identifier": 7, "address": 1, "payload": [3, 0, 10]},
        "target_protocol": "modbus-rtu",
    })
    assert result.frame == {
        "protocol": "modbus-rtu",
        "address": 1,
        "payload": [3, 0, 10],
    }
    assert "preserved" in result.warnings[0]


def test_signals_mapping_and_mutable_state():
    source = {
        "protocol": "ethernet",
        "payload": [1],
        "signals": {"speed": 42},
        "metadata": {"k": "v"},
    }
    result = convert_frame({
        "source": source,
        "target_protocol": "ethercat",
        "options": {"mapping": {"speed": "velocity"}},
    })
    result.frame.payload.append(9)
    result.frame.signals["velocity"] = 2
    assert source == {
        "protocol": "ethernet",
        "payload": [1],
        "signals": {"speed": 42},
        "metadata": {"k": "v"},
    }


def test_device_ids_and_conflicts():
    result = convert_message({
        "source": {
            "device_id": "0x10",
            "message": {"protocol": "lin", "identifier": 1, "payload": [3, 0]},
        },
        "target": {"protocol": "modbus-tcp"},
    })
    assert result.message.address == 16

    result = convert_message({
        "source": {"message": {"protocol": "modbus-tcp", "address": 9, "payload": [3, 0]}},
        "target": {"protocol": "modbus-rtu", "device_id": 2},
    })
    assert result.message.address == 9
    assert any("message address 9" in warning for warning in result.warnings)


def test_custom_required_context_and_registry():
    converter = create_converter({
        "adapters": {
            "ethercat": create_adapter({
                "protocol": "ethercat",
                "max_payload": 1486,
                "required_context": ["profile"],
            }),
        },
    })
    with pytest.raises(FieldbridgeError) as exc:
        converter.convert_message({
            "source": {"message": {"protocol": "can", "identifier": 1, "payload": [1]}},
            "target": {"protocol": "ethercat"},
        })
    assert exc.value.code == "MISSING_CONTEXT"

    result = converter.convert_message({
        "source": {"message": {"protocol": "can", "identifier": 1, "payload": [1]}},
        "target": {"protocol": "ethercat", "context": {"profile": "profile-a"}},
    })
    assert result.message.metadata["profile"] == "profile-a"
    assert adapters.ethercat.required_context == ()


def test_validation_and_try_api():
    with pytest.raises(FieldbridgeError) as exc:
        validate_frame({"protocol": "ethernet", "payload": [256]})
    assert exc.value.code == "INVALID_PAYLOAD"

    result = try_convert_frame({
        "source": {"protocol": "can", "identifier": 1, "payload": [1] * 9, "metadata": {"fd": False}},
        "target_protocol": "lin",
    })
    assert result.ok is False
    assert result.error.code == "INVALID_PAYLOAD"
