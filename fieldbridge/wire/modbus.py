from ..adapters.modbus import modbus_rtu_adapter, modbus_tcp_adapter
from ..core.errors import FieldbridgeError
from ..core.types import AttrDict
from .bytes import to_bytes, expect_protocol, meta_int, truncated


def crc16_modbus(data, start=0, end=None):
    if end is None:
        end = len(data)
    crc = 0xffff
    for index in range(start, end):
        crc ^= data[index]
        for _ in range(8):
            crc = (crc >> 1) ^ 0xa001 if (crc & 1) else crc >> 1
    return crc


def parse_modbus_tcp_stream(input):
    data = to_bytes(input, "modbus-tcp")
    frames = []
    offset = 0
    while len(data) - offset >= 6:
        transaction_id = int.from_bytes(data[offset:offset + 2], "big")
        protocol_id = int.from_bytes(data[offset + 2:offset + 4], "big")
        length = int.from_bytes(data[offset + 4:offset + 6], "big")
        if protocol_id != 0:
            raise FieldbridgeError("INVALID_FRAME",
                                   f"modbus-tcp protocol identifier must be 0, got {protocol_id}",
                                   protocol="modbus-tcp")
        if length < 2 or length > 254:
            raise FieldbridgeError("INVALID_FRAME",
                                   f"modbus-tcp MBAP length must be 2..254, got {length}",
                                   protocol="modbus-tcp")
        if len(data) - offset < 6 + length:
            break
        frame = modbus_tcp_adapter.decode({
            "protocol": "modbus-tcp",
            "address": data[offset + 6],
            "payload": list(data[offset + 7:offset + 6 + length]),
            "metadata": {"transactionId": transaction_id},
        })
        frames.append(AttrDict(frame))
        offset += 6 + length
    return AttrDict(frames=frames, rest=data[offset:])


def parse_modbus_tcp(input):
    data = to_bytes(input, "modbus-tcp")
    result = parse_modbus_tcp_stream(data)
    if not result["frames"]:
        need = 6 + int.from_bytes(data[4:6], "big") if len(data) >= 6 else 9
        raise truncated("modbus-tcp", "ADU", need, len(data))
    if len(result["frames"]) > 1:
        raise FieldbridgeError("INVALID_FRAME",
                               f"modbus-tcp input contains {len(result['frames'])} ADUs; use parse_modbus_tcp_stream",
                               protocol="modbus-tcp")
    if result["rest"]:
        raise FieldbridgeError("INVALID_FRAME",
                               f"modbus-tcp input has {len(result['rest'])} trailing bytes",
                               protocol="modbus-tcp")
    return result["frames"][0]


def serialize_modbus_tcp(frame):
    if frame is None or not hasattr(frame, "get"):
        raise FieldbridgeError("INVALID_FRAME", "frame must be an object")
    expect_protocol(frame, "modbus-tcp")
    valid = modbus_tcp_adapter.encode(frame)
    transaction_id = meta_int(valid, "transactionId", 0, 0xffff, 0)
    out = bytearray(7 + len(valid["payload"]))
    out[0:2] = transaction_id.to_bytes(2, "big")
    out[2:4] = (0).to_bytes(2, "big")
    out[4:6] = (1 + len(valid["payload"])).to_bytes(2, "big")
    out[6] = valid["address"]
    out[7:] = bytes(valid["payload"])
    return bytes(out)


def parse_modbus_rtu(input):
    data = to_bytes(input, "modbus-rtu")
    if len(data) < 4:
        raise truncated("modbus-rtu", "ADU (address, function code, CRC)", 4, len(data))
    expected = crc16_modbus(data, 0, len(data) - 2)
    received = data[-2] | (data[-1] << 8)
    if expected != received:
        raise FieldbridgeError(
            "CHECKSUM_MISMATCH",
            f"modbus-rtu CRC mismatch: frame has 0x{received:04x}, expected 0x{expected:04x}",
            protocol="modbus-rtu",
        )
    frame = modbus_rtu_adapter.decode({
        "protocol": "modbus-rtu",
        "address": data[0],
        "payload": list(data[1:-2]),
    })
    return AttrDict(frame)


def serialize_modbus_rtu(frame):
    expect_protocol(frame, "modbus-rtu")
    valid = modbus_rtu_adapter.encode(frame)
    out = bytearray(len(valid["payload"]) + 3)
    out[0] = valid["address"]
    out[1:-2] = bytes(valid["payload"])
    crc = crc16_modbus(out, 0, len(out) - 2)
    out[-2] = crc & 0xff
    out[-1] = crc >> 8
    return bytes(out)


crc16Modbus = crc16_modbus
parseModbusTcpStream = parse_modbus_tcp_stream
parseModbusTcp = parse_modbus_tcp
serializeModbusTcp = serialize_modbus_tcp
parseModbusRtu = parse_modbus_rtu
serializeModbusRtu = serialize_modbus_rtu
