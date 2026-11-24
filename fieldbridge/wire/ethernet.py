from ..adapters.ethercat import ethercat_adapter
from ..adapters.ethernet import ethernet_adapter
from ..adapters.profinet import profinet_adapter
from ..core.errors import FieldbridgeError
from ..core.types import AttrDict
from .bytes import (
    to_bytes, expect_protocol, meta_int, read_mac, require_value,
    truncated, write_mac,
)

EtherType = AttrDict({
    "VLAN": 0x8100,
    "PROFINET": 0x8892,
    "ETHERCAT": 0x88a4,
})

EthercatCommand = AttrDict({
    "NOP": 0, "APRD": 1, "APWR": 2, "APRW": 3,
    "FPRD": 4, "FPWR": 5, "FPRW": 6, "BRD": 7,
    "BWR": 8, "BRW": 9, "LRD": 10, "LWR": 11,
    "LRW": 12, "ARMW": 13, "FRMW": 14,
})

HEADER = 14
MIN_FRAME = 60
BROADCAST_MAC = 0xffffffffffff
DATAGRAM_HEADER = 10
WKC = 2
MAX_DATAGRAMS_LENGTH = 1500 - 2


def read_header(data, protocol):
    if len(data) < HEADER:
        raise truncated(protocol, "Ethernet header", HEADER, len(data))
    destination = read_mac(data, 0)
    source = read_mac(data, 6)
    ether_type = int.from_bytes(data[12:14], "big")
    offset = HEADER
    metadata = {}
    if ether_type == EtherType["VLAN"]:
        if len(data) < HEADER + 4:
            raise truncated(protocol, "802.1Q header", HEADER + 4, len(data))
        tci = int.from_bytes(data[14:16], "big")
        metadata["vlanId"] = tci & 0x0fff
        metadata["vlanPriority"] = tci >> 13
        ether_type = int.from_bytes(data[16:18], "big")
        offset += 4
    return {
        "destination": destination,
        "source": source,
        "ether_type": ether_type,
        "offset": offset,
        "metadata": metadata,
    }


def header_length(frame):
    metadata = frame.get("metadata") or {}
    tagged = metadata.get("vlanId") is not None or metadata.get("vlan_id") is not None
    return HEADER + 4 if tagged else HEADER


def allocate(frame, body_length):
    return bytearray(max(MIN_FRAME, header_length(frame) + body_length))


def write_header(out, frame, destination, source, ether_type):
    write_mac(out, 0, destination)
    write_mac(out, 6, source)
    vlan_id = meta_int(frame, "vlanId", 0, 4095)
    if vlan_id is None:
        out[12:14] = ether_type.to_bytes(2, "big")
        return HEADER
    priority = meta_int(frame, "vlanPriority", 0, 7, 0)
    out[12:14] = EtherType["VLAN"].to_bytes(2, "big")
    out[14:16] = ((priority << 13) | vlan_id).to_bytes(2, "big")
    out[16:18] = ether_type.to_bytes(2, "big")
    return HEADER + 4


def expect_ether_type(header, ether_type, protocol):
    if header["ether_type"] != ether_type:
        raise FieldbridgeError(
            "INVALID_FRAME",
            f'not a {protocol} frame: EtherType 0x{header["ether_type"]:04x}, '
            f"expected 0x{ether_type:x}",
            protocol=protocol,
        )


def parse_ethernet(input):
    data = to_bytes(input, "ethernet")
    header = read_header(data, "ethernet")
    payload = data[header["offset"]:]
    if header["ether_type"] <= 1500:
        if len(payload) < header["ether_type"]:
            raise truncated("ethernet", "802.3 payload",
                            header["offset"] + header["ether_type"], len(data))
        payload = payload[:header["ether_type"]]
    frame = {
        "protocol": "ethernet",
        "destination_address": header["destination"],
        "source_address": header["source"],
        "identifier": header["ether_type"],
        "payload": list(payload),
    }
    if header["metadata"]:
        frame["metadata"] = header["metadata"]
    return AttrDict(ethernet_adapter.decode(frame))


def serialize_ethernet(frame):
    expect_protocol(frame, "ethernet")
    valid = ethernet_adapter.encode(frame)
    destination = require_value(valid.get("destination_address"), "ethernet",
                                "destination_address", "a destination MAC (destinationAddress)")
    source = require_value(valid.get("source_address"), "ethernet",
                           "source_address", "a source MAC (sourceAddress)")
    ether_type = require_value(valid.get("identifier"), "ethernet",
                               "identifier", "an EtherType (identifier)")
    out = allocate(valid, len(valid["payload"]))
    offset = write_header(out, valid, destination, source, ether_type)
    out[offset:offset + len(valid["payload"])] = bytes(valid["payload"])
    return bytes(out)


def parse_profinet(input):
    data = to_bytes(input, "profinet")
    header = read_header(data, "profinet")
    expect_ether_type(header, EtherType["PROFINET"], "profinet")
    if len(data) < header["offset"] + 2:
        raise truncated("profinet", "FrameID", header["offset"] + 2, len(data))
    frame = {
        "protocol": "profinet",
        "destination_address": header["destination"],
        "source_address": header["source"],
        "identifier": int.from_bytes(data[header["offset"]:header["offset"] + 2], "big"),
        "payload": list(data[header["offset"] + 2:]),
    }
    if header["metadata"]:
        frame["metadata"] = header["metadata"]
    return AttrDict(profinet_adapter.decode(frame))


def serialize_profinet(frame):
    expect_protocol(frame, "profinet")
    valid = profinet_adapter.encode(frame)
    destination = require_value(valid.get("destination_address"), "profinet",
                                "destination_address", "a destination MAC (destinationAddress)")
    source = require_value(valid.get("source_address"), "profinet",
                           "source_address", "a source MAC (sourceAddress)")
    frame_id = require_value(valid.get("identifier"), "profinet",
                             "identifier", "a FrameID (identifier)")
    out = allocate(valid, 2 + len(valid["payload"]))
    offset = write_header(out, valid, destination, source, EtherType["PROFINET"])
    out[offset:offset + 2] = frame_id.to_bytes(2, "big")
    out[offset + 2:offset + 2 + len(valid["payload"])] = bytes(valid["payload"])
    return bytes(out)


def addressing(command):
    if command in (1, 2, 3, 13):
        return "position"
    if command in (4, 5, 6, 14):
        return "configured"
    if command in (7, 8, 9):
        return "broadcast"
    if command in (10, 11, 12):
        return "logical"
    return "none"


def parse_ethercat(input):
    data = to_bytes(input, "ethercat")
    header = read_header(data, "ethercat")
    expect_ether_type(header, EtherType["ETHERCAT"], "ethercat")
    if len(data) < header["offset"] + 2:
        raise truncated("ethercat", "EtherCAT header", header["offset"] + 2, len(data))
    word = int.from_bytes(data[header["offset"]:header["offset"] + 2], "little")
    length = word & 0x07ff
    frame_type = word >> 12
    if frame_type != 1:
        raise FieldbridgeError("UNSUPPORTED_FEATURE",
                               f"EtherCAT frame type {frame_type} is not supported (only datagrams, type 1)",
                               protocol="ethercat")
    end = header["offset"] + 2 + length
    if end > len(data):
        raise truncated("ethercat", "datagrams", end, len(data))

    frames = []
    pos = header["offset"] + 2
    while True:
        if pos + DATAGRAM_HEADER > end:
            raise truncated("ethercat", "datagram header", pos + DATAGRAM_HEADER, end)
        command = data[pos]
        len_word = int.from_bytes(data[pos + 6:pos + 8], "little")
        data_length = len_word & 0x07ff
        more = bool(len_word & 0x8000)
        if pos + DATAGRAM_HEADER + data_length + WKC > end:
            raise truncated("ethercat", "datagram",
                            pos + DATAGRAM_HEADER + data_length + WKC, end)
        adp = int.from_bytes(data[pos + 2:pos + 4], "little")
        ado = int.from_bytes(data[pos + 4:pos + 6], "little")
        metadata = dict(header["metadata"])
        metadata.update({
            "ethernetDestination": header["destination"],
            "ethernetSource": header["source"],
            "command": command,
            "index": data[pos + 1],
            "irq": int.from_bytes(data[pos + 8:pos + 10], "little"),
            "workingCounter": int.from_bytes(
                data[pos + DATAGRAM_HEADER + data_length:pos + DATAGRAM_HEADER + data_length + WKC],
                "little",
            ),
            "circulated": bool(len_word & 0x4000),
        })
        frame = {
            "protocol": "ethercat",
            "payload": list(data[pos + DATAGRAM_HEADER:pos + DATAGRAM_HEADER + data_length]),
            "metadata": metadata,
        }
        kind = addressing(command)
        if kind == "configured":
            frame["address"] = adp
            metadata["offset"] = ado
        elif kind == "position":
            metadata["position"] = adp - 0x10000 if adp > 0x7fff else adp
            metadata["offset"] = ado
        elif kind == "broadcast":
            metadata["adp"] = adp
            metadata["offset"] = ado
        elif kind == "logical":
            metadata["logicalAddress"] = int.from_bytes(data[pos + 2:pos + 6], "little")
        else:
            metadata["adp"] = adp
            metadata["ado"] = ado
        frames.append(AttrDict(ethercat_adapter.decode(frame)))
        pos += DATAGRAM_HEADER + data_length + WKC
        if not more:
            break
    return frames


def serialize_ethercat(datagrams, destination=None, source=None, **kwargs):
    if isinstance(destination, dict):
        options = destination
        destination = options.get("destination")
        source = options.get("source")
    if not isinstance(datagrams, (list, tuple)) or not datagrams:
        raise FieldbridgeError("INVALID_FRAME",
                               "serializeEthercat needs at least one datagram",
                               protocol="ethercat")
    valid = []
    for datagram in datagrams:
        expect_protocol(datagram, "ethercat")
        valid.append(ethercat_adapter.encode(datagram))
    first = valid[0]
    body_length = sum(DATAGRAM_HEADER + len(d["payload"]) + WKC for d in valid)
    if body_length > MAX_DATAGRAMS_LENGTH:
        raise FieldbridgeError("PAYLOAD_TOO_LARGE",
                               f"EtherCAT datagrams total {body_length} bytes; maximum is {MAX_DATAGRAMS_LENGTH}",
                               protocol="ethercat")
    if destination is None:
        destination = meta_int(first, "ethernetDestination", 0, BROADCAST_MAC, BROADCAST_MAC)
    source = source if source is not None else meta_int(first, "ethernetSource", 0, BROADCAST_MAC)
    source = require_value(source, "ethercat", "metadata.ethernetSource",
                           "a source MAC (options.source or metadata.ethernetSource)")

    out = allocate(first, 2 + body_length)
    pos = write_header(out, first, destination, source, EtherType["ETHERCAT"])
    out[pos:pos + 2] = ((1 << 12) | body_length).to_bytes(2, "little")
    pos += 2
    for index, datagram in enumerate(valid):
        command = require_value(meta_int(datagram, "command", 0, 14), "ethercat",
                                "metadata.command", "a datagram command (metadata.command)")
        out[pos] = command
        out[pos + 1] = meta_int(datagram, "index", 0, 0xff, 0)
        kind = addressing(command)
        if kind == "configured":
            address = require_value(datagram.get("address"), "ethercat", "address",
                                    "a station address (address) for configured addressing")
            out[pos + 2:pos + 4] = address.to_bytes(2, "little")
            out[pos + 4:pos + 6] = meta_int(datagram, "offset", 0, 0xffff, 0).to_bytes(2, "little")
        elif kind == "position":
            position = meta_int(datagram, "position", -0x8000, 0x7fff, 0)
            out[pos + 2:pos + 4] = (position & 0xffff).to_bytes(2, "little")
            out[pos + 4:pos + 6] = meta_int(datagram, "offset", 0, 0xffff, 0).to_bytes(2, "little")
        elif kind == "broadcast":
            out[pos + 2:pos + 4] = meta_int(datagram, "adp", 0, 0xffff, 0).to_bytes(2, "little")
            out[pos + 4:pos + 6] = meta_int(datagram, "offset", 0, 0xffff, 0).to_bytes(2, "little")
        elif kind == "logical":
            logical = require_value(meta_int(datagram, "logicalAddress", 0, 0xffffffff),
                                    "ethercat", "metadata.logicalAddress",
                                    "a logical address (metadata.logicalAddress)")
            out[pos + 2:pos + 6] = logical.to_bytes(4, "little")
        else:
            out[pos + 2:pos + 4] = meta_int(datagram, "adp", 0, 0xffff, 0).to_bytes(2, "little")
            out[pos + 4:pos + 6] = meta_int(datagram, "ado", 0, 0xffff, 0).to_bytes(2, "little")
        more = 0x8000 if index < len(valid) - 1 else 0
        circulated = 0x4000 if (datagram.get("metadata") or {}).get("circulated") is True else 0
        len_word = len(datagram["payload"]) | circulated | more
        out[pos + 6:pos + 8] = len_word.to_bytes(2, "little")
        out[pos + 8:pos + 10] = meta_int(datagram, "irq", 0, 0xffff, 0).to_bytes(2, "little")
        out[pos + 10:pos + 10 + len(datagram["payload"])] = bytes(datagram["payload"])
        out[pos + 10 + len(datagram["payload"]):pos + 12 + len(datagram["payload"])] = \
            meta_int(datagram, "workingCounter", 0, 0xffff, 0).to_bytes(2, "little")
        pos += DATAGRAM_HEADER + len(datagram["payload"]) + WKC
    return bytes(out)


def parse_ethernet_auto(input):
    data = to_bytes(input, "ethernet")
    header = read_header(data, "ethernet")
    if header["ether_type"] == EtherType["PROFINET"]:
        return [parse_profinet(data)]
    if header["ether_type"] == EtherType["ETHERCAT"]:
        return parse_ethercat(data)
    return [parse_ethernet(data)]


parseEthernet = parse_ethernet
serializeEthernet = serialize_ethernet
parseProfinet = parse_profinet
serializeProfinet = serialize_profinet
parseEthercat = parse_ethercat
serializeEthercat = serialize_ethercat
parseEthernetAuto = parse_ethernet_auto
