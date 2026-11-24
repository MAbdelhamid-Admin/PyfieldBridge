import re

from ..adapters.can import can_adapter
from ..core.errors import FieldbridgeError
from ..core.types import AttrDict
from .bytes import to_bytes, expect_protocol, meta_int

CAN_EFF_FLAG = 0x80000000
CAN_RTR_FLAG = 0x40000000
CAN_ERR_FLAG = 0x20000000
CAN_EFF_MASK = 0x1fffffff
CAN_SFF_MASK = 0x7ff
CANFD_BRS = 0x01
CANFD_ESI = 0x02
CANFD_FDF = 0x04

CAN_MTU = 16
CANFD_MTU = 72
HEX = re.compile(r"^[0-9a-f]*$", re.I)


def _metadata_value(metadata, snake, camel=None):
    if metadata is None:
        return None
    if snake in metadata:
        return metadata[snake]
    if camel and camel in metadata:
        return metadata[camel]
    return None


def can_frame(identifier, payload, metadata):
    return AttrDict(can_adapter.decode({
        "protocol": "can",
        "identifier": identifier,
        "payload": list(payload),
        "metadata": dict(metadata),
    }))


def frame_flags(frame):
    metadata = frame.get("metadata") or {}
    extended = metadata.get("extended")
    if extended is None:
        extended = frame["identifier"] > CAN_SFF_MASK
    fd = metadata.get("fd")
    if fd is None:
        fd = len(frame["payload"]) > 8
    rtr = metadata.get("rtr") is True
    if rtr and fd:
        raise FieldbridgeError("INVALID_FIELD",
                               "CAN FD has no remote frames",
                               protocol="can", field="metadata.rtr")
    if rtr and len(frame["payload"]) > 0:
        raise FieldbridgeError("INVALID_PAYLOAD",
                               "CAN remote frames carry no data",
                               protocol="can", field="payload")
    return {
        "extended": extended is True,
        "fd": fd is True,
        "rtr": rtr,
        "brs": metadata.get("brs") is True,
        "esi": metadata.get("esi") is True,
    }


def parse_socket_can(input, little_endian=True, **kwargs):
    if isinstance(little_endian, dict):
        options = little_endian
        little_endian = options.get("little_endian", options.get("littleEndian", True))
    if "littleEndian" in kwargs:
        little_endian = kwargs["littleEndian"]
    options = kwargs.get("options")
    if isinstance(options, dict) and "littleEndian" in options:
        little_endian = options["littleEndian"]
    data = to_bytes(input, "can")
    if len(data) not in (CAN_MTU, CANFD_MTU):
        raise FieldbridgeError("INVALID_FRAME",
                               f"SocketCAN frame must be {CAN_MTU} or {CANFD_MTU} bytes, got {len(data)}",
                               protocol="can")
    raw_id = int.from_bytes(data[0:4], "little" if little_endian else "big")
    if raw_id & CAN_ERR_FLAG:
        raise FieldbridgeError("UNSUPPORTED_FEATURE",
                               "CAN error frames are not supported",
                               protocol="can")
    extended = bool(raw_id & CAN_EFF_FLAG)
    identifier = (raw_id & CAN_EFF_MASK) if extended else (raw_id & CAN_SFF_MASK)
    length = data[4]
    if len(data) == CAN_MTU:
        if length > 8:
            raise FieldbridgeError("INVALID_FRAME",
                                   f"classic CAN length {length} exceeds 8",
                                   protocol="can")
        if raw_id & CAN_RTR_FLAG:
            return can_frame(identifier, [], {
                "extended": extended, "fd": False, "rtr": True, "rtrLength": length,
            })
        return can_frame(identifier, data[8:8 + length], {
            "extended": extended, "fd": False,
        })
    if length > 64:
        raise FieldbridgeError("INVALID_FRAME",
                               f"CAN FD length {length} exceeds 64",
                               protocol="can")
    flags = data[5]
    return can_frame(identifier, data[8:8 + length], {
        "extended": extended,
        "fd": True,
        "brs": bool(flags & CANFD_BRS),
        "esi": bool(flags & CANFD_ESI),
    })


def serialize_socket_can(frame, little_endian=True, **kwargs):
    if isinstance(little_endian, dict):
        options = little_endian
        little_endian = options.get("little_endian", options.get("littleEndian", True))
    if "littleEndian" in kwargs:
        little_endian = kwargs["littleEndian"]
    options = kwargs.get("options")
    if isinstance(options, dict) and "littleEndian" in options:
        little_endian = options["littleEndian"]
    expect_protocol(frame, "can")
    valid = can_adapter.encode(frame)
    flags = frame_flags(valid)
    data = bytearray(CANFD_MTU if flags["fd"] else CAN_MTU)
    raw_id = valid["identifier"]
    if flags["extended"]:
        raw_id |= CAN_EFF_FLAG
    if flags["rtr"]:
        raw_id |= CAN_RTR_FLAG
    data[0:4] = (raw_id & 0xffffffff).to_bytes(4, "little" if little_endian else "big")
    if flags["rtr"]:
        length = meta_int(valid, "rtrLength", 0, 8, 0)
    else:
        length = len(valid["payload"])
    data[4] = length
    if flags["fd"]:
        data[5] = CANFD_FDF | (CANFD_BRS if flags["brs"] else 0) | (CANFD_ESI if flags["esi"] else 0)
    data[8:8 + len(valid["payload"])] = bytes(valid["payload"])
    return bytes(data)


def hex_to_bytes(hex_text, line):
    clean = hex_text.replace(".", "")
    if len(clean) % 2 or not HEX.fullmatch(clean):
        raise FieldbridgeError("INVALID_FRAME",
                               f'invalid candump data in "{line}"',
                               protocol="can")
    return [int(clean[index:index + 2], 16) for index in range(0, len(clean), 2)]


def parse_can_id(id_text, line):
    if len(id_text) not in (3, 8) or not HEX.fullmatch(id_text):
        raise FieldbridgeError("INVALID_FRAME",
                               f'invalid candump CAN ID in "{line}"',
                               protocol="can")
    return int(id_text, 16), len(id_text) == 8


def parse_candump_display(tokens, metadata, line):
    interface, id_text, length_text, *rest = tokens
    metadata["interface"] = interface
    identifier, extended = parse_can_id(id_text, line)
    metadata["extended"] = extended
    digits = length_text[1:-1]
    length = int(digits)
    if " ".join(rest).lower() == "remote request":
        metadata.update({"fd": False, "rtr": True, "rtrLength": length})
        return can_frame(identifier, [], metadata)
    fd = len(digits) == 2
    metadata["fd"] = fd
    if len(rest) != length or any(not re.fullmatch(r"[0-9a-f]{2}", b, re.I) for b in rest):
        raise FieldbridgeError("INVALID_FRAME",
                               f'candump line declares {length} bytes but has "{ " ".join(rest) }": "{line}"',
                               protocol="can")
    payload = [int(byte, 16) for byte in rest]
    return can_frame(identifier, payload, metadata)


def parse_candump_line(line):
    if not isinstance(line, str):
        raise FieldbridgeError("INVALID_FRAME", "candump line must be a string", protocol="can")
    tokens = line.strip().split()
    metadata = {}
    if tokens and re.fullmatch(r"\(\d+(?:\.\d+)?\)", tokens[0]):
        metadata["timestamp"] = float(tokens[0][1:-1])
        tokens = tokens[1:]
    if len(tokens) >= 3 and re.fullmatch(r"\[\d{1,2}\]", tokens[2]):
        return parse_candump_display(tokens, metadata, line)

    if len(tokens) == 2:
        metadata["interface"] = tokens[0]
        frame_text = tokens[1]
    elif len(tokens) == 1 and tokens[0]:
        frame_text = tokens[0]
    else:
        raise FieldbridgeError("INVALID_FRAME",
                               f'unrecognised candump line "{line}"',
                               protocol="can")

    hash_index = frame_text.find("#")
    identifier, extended = parse_can_id(frame_text[:hash_index] if hash_index >= 0 else "", line)
    metadata["extended"] = extended
    body = frame_text[hash_index + 1:] if hash_index >= 0 else ""
    if body.startswith("#"):
        if len(body) < 2:
            raise FieldbridgeError("INVALID_FRAME",
                                   f'missing CAN FD flags in "{line}"',
                                   protocol="can")
        try:
            flags = int(body[1], 16)
        except ValueError:
            raise FieldbridgeError("INVALID_FRAME",
                                   f'missing CAN FD flags in "{line}"',
                                   protocol="can")
        metadata.update({
            "fd": True,
            "brs": bool(flags & CANFD_BRS),
            "esi": bool(flags & CANFD_ESI),
        })
        return can_frame(identifier, hex_to_bytes(body[2:], line), metadata)
    if re.fullmatch(r"r\d?", body, re.I):
        metadata.update({
            "fd": False,
            "rtr": True,
            "rtrLength": int(body[1]) if len(body) > 1 else 0,
        })
        return can_frame(identifier, [], metadata)
    metadata["fd"] = False
    return can_frame(identifier, hex_to_bytes(body, line), metadata)


def format_candump_line(frame):
    expect_protocol(frame, "can")
    valid = can_adapter.encode(frame)
    flags = frame_flags(valid)
    identifier = format(valid["identifier"], "x").upper().zfill(8 if flags["extended"] else 3)
    data = "".join(format(byte, "02X") for byte in valid["payload"])
    if flags["rtr"]:
        length = meta_int(valid, "rtrLength", 0, 8, 0)
        body = f"R{length if length > 0 else ''}"
    elif flags["fd"]:
        fd_flags = (CANFD_BRS if flags["brs"] else 0) | (CANFD_ESI if flags["esi"] else 0)
        body = f"#{format(fd_flags, 'X')}{data}"
    else:
        body = data
    text = f"{identifier}#{body}"
    metadata = valid.get("metadata") or {}
    timestamp = metadata.get("timestamp")
    interface = metadata.get("interface")
    if isinstance(timestamp, (int, float)) and isinstance(interface, str):
        return f"({timestamp:.6f}) {interface} {text}"
    if isinstance(interface, str):
        return f"{interface} {text}"
    return text


parseSocketCan = parse_socket_can
serializeSocketCan = serialize_socket_can
parseCandumpLine = parse_candump_line
formatCandumpLine = format_candump_line
