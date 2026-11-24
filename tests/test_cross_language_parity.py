import json
import os
import subprocess
from pathlib import Path

import pytest

from fieldbridge import (
    FieldbridgeError,
    convert_frame,
    convert_message,
    create_adapter,
    create_converter,
)
from fieldbridge import try_convert_frame
from fieldbridge.wire import (
    CAN_MTU,
    crc16_modbus,
    format_candump_line,
    parse_candump_line,
    parse_ethercat,
    parse_ethernet,
    parse_modbus_rtu,
    parse_modbus_tcp,
    parse_modbus_tcp_stream,
    parse_socket_can,
    serialize_ethercat,
    serialize_modbus_rtu,
    serialize_modbus_tcp,
    serialize_socket_can,
)


PROJECT = Path(__file__).resolve().parents[1]
TS_PROJECT = Path(os.environ.get("FIELD_BRIDGE_TS", PROJECT.parent / "typescript_fieldbridge"))
CAMEL_KEYS = {
    "source_address": "sourceAddress",
    "destination_address": "destinationAddress",
    "target_protocol": "targetProtocol",
    "target_device_id": "targetDeviceId",
    "device_id": "deviceId",
    "rtr_length": "rtrLength",
    "transaction_id": "transactionId",
    "ethernet_destination": "ethernetDestination",
    "ethernet_source": "ethernetSource",
    "working_counter": "workingCounter",
    "logical_address": "logicalAddress",
    "vlan_id": "vlanId",
    "vlan_priority": "vlanPriority",
}


def normalize(value):
    if isinstance(value, FieldbridgeError):
        return {
            "code": value.code,
            "protocol": value.protocol,
            "field": value.field,
        }
    if isinstance(value, dict):
        return {CAMEL_KEYS.get(key, key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if hasattr(value, "get"):
        return normalize(dict(value))
    return value


def result_json(value):
    if isinstance(value, FieldbridgeError):
        return {
            "code": value.code,
            "protocol": value.protocol,
            "field": value.field,
        }
    if hasattr(value, "dict"):
        value = value.dict()
    if hasattr(value, "items"):
        value = dict(value)
    return normalize(value)


def python_cases():
    converter = create_converter({
        "adapters": {
            "ethercat": create_adapter({
                "protocol": "ethercat",
                "maxPayload": 1486,
                "requiredContext": ["profile"],
            }),
        },
    })

    def safe_frame(fn):
        try:
            return {"ok": True, "value": result_json(fn())}
        except Exception as error:
            return {
                "ok": False,
                "error": {
                    "code": getattr(error, "code", None),
                    "protocol": getattr(error, "protocol", None),
                    "field": getattr(error, "field", None),
                },
            }

    stream = bytes.fromhex("0001000000061103006B0003" "000200000006110600010003" "00030000000611")
    stream_result = parse_modbus_tcp_stream(stream)
    classic = bytearray(CAN_MTU)
    classic[0:4] = (0x123).to_bytes(4, "little")
    classic[4] = 3
    classic[8:11] = bytes([0xde, 0xad, 0xbe])
    socket_frame = parse_socket_can(bytes(classic))
    candump_frame = parse_candump_line("(1436509052.249713) vcan0 123#DEADBEEF")
    ethercat_wire = serialize_ethercat([{
        "protocol": "ethercat",
        "payload": [0, 0],
        "metadata": {"command": 1, "position": -2, "offset": 0x10, "ethernetSource": 1},
    }])

    return {
        "can_to_modbus": result_json(convert_frame({
            "source": {"protocol": "can", "identifier": 7, "address": 1, "payload": [3, 0, 10]},
            "targetProtocol": "modbus-rtu",
        })),
        "signals": result_json(convert_frame({
            "source": {"protocol": "ethernet", "payload": [1], "signals": {"speed": 42}},
            "targetProtocol": "ethercat",
            "options": {"mapping": {"speed": "velocity", "temp": "temperature"}},
        })),
        "numeric_device_id": result_json(convert_message({
            "source": {"device_id": "0x10", "message": {"protocol": "lin", "identifier": 1, "payload": [3, 0]}},
            "target": {"protocol": "modbus-tcp"},
        })),
        "message_address_conflict": result_json(convert_message({
            "source": {"message": {"protocol": "modbus-tcp", "address": 9, "payload": [3, 0]}},
            "target": {"protocol": "modbus-rtu", "device_id": 2},
        })),
        "source_context_conflict": result_json(convert_message({
            "source": {"context": {"line": "A", "site": "x"}, "message": {"protocol": "ethernet", "payload": [1], "metadata": {"line": "B"}}},
            "target": {"protocol": "ethercat"},
        })),
        "boolean_metadata_conflict": result_json(convert_message({
            "source": {"message": {"protocol": "ethernet", "payload": [1], "metadata": {"flag": True}}},
            "target": {"protocol": "profinet", "context": {"flag": False}},
        })),
        "empty_mapping": result_json(convert_frame({
            "source": {"protocol": "ethernet", "payload": [1], "signals": {"speed": 42}},
            "targetProtocol": "ethercat",
            "options": {"mapping": {}},
        })),
        "dropped_fields": result_json(convert_frame({
            "source": {"protocol": "ethernet", "sourceAddress": 10, "destinationAddress": 20,
                       "identifier": 2048, "payload": [1, 2, 3]},
            "targetProtocol": "can",
        })),
        "invalid_device_id": safe_frame(lambda: convert_frame({
            "source": {"protocol": "ethernet", "payload": [1]},
            "target_protocol": "ethercat",
            "options": {"target_device_id": "gateway-1"},
        })),
        "invalid_payload": safe_frame(lambda: convert_frame({
            "source": {"protocol": "can", "identifier": 1, "payload": [0] * 9, "metadata": {"fd": False}},
            "target_protocol": "lin",
        })),
        "try_invalid": result_json(try_convert_frame({
            "source": {"protocol": "can", "identifier": 1, "payload": [0] * 9, "metadata": {"fd": False}},
            "target_protocol": "lin",
        })),
        "required_context": safe_frame(lambda: converter.convert_message({
            "source": {"message": {"protocol": "can", "identifier": 1, "payload": [1]}},
            "target": {"protocol": "ethercat"},
        })),
        "modbus_rtu": {
            "frame": result_json(parse_modbus_rtu(bytes.fromhex("1103006B00037687"))),
            "bytes": serialize_modbus_rtu(parse_modbus_rtu(bytes.fromhex("1103006B00037687"))).hex(),
            "crc": crc16_modbus(b"123456789"),
        },
        "modbus_tcp_stream": {
            "frames": [result_json(frame) for frame in stream_result.frames],
            "rest": stream_result.rest.hex(),
            "serialized": serialize_modbus_tcp(parse_modbus_tcp(bytes.fromhex("0001000000061103006B0003"))).hex(),
        },
        "socketcan": {
            "frame": result_json(socket_frame),
            "bytes": serialize_socket_can(socket_frame).hex(),
        },
        "candump": {
            "frame": result_json(candump_frame),
            "formatted": format_candump_line(candump_frame),
        },
        "ethernet": {
            "frame": result_json(parse_ethernet(bytes.fromhex("0102030405060A0B0C0D0E0F08004500001C"))),
        },
        "ethercat": {
            "frames": [result_json(frame) for frame in parse_ethercat(ethercat_wire)],
            "bytes": ethercat_wire.hex(),
        },
    }


def test_typeScript_and_python_results_match():
    tsx = TS_PROJECT / "node_modules" / ".bin" / ("tsx.cmd" if os.name == "nt" else "tsx")
    if not tsx.exists():
        pytest.skip(
            "TypeScript fieldbridge checkout not found; set FIELD_BRIDGE_TS to run the cross-language parity test"
        )
    node = subprocess.run(
        [str(tsx), str(PROJECT / "tests" / "parity.ts")],
        cwd=PROJECT,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    typescript = json.loads(node.stdout)
    python = python_cases()
    assert python == typescript
