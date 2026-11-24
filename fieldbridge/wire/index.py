from ..core.errors import FieldbridgeError
from ..core.validation import assert_protocol
from .bytes import to_bytes
from .modbus import (
    crc16_modbus, parse_modbus_rtu, parse_modbus_tcp,
    parse_modbus_tcp_stream, serialize_modbus_rtu, serialize_modbus_tcp,
)
from .can import (
    CAN_MTU, CANFD_MTU, parse_socket_can, serialize_socket_can,
    parse_candump_line, format_candump_line,
)
from .ethernet import (
    EtherType, EthercatCommand, parse_ethercat, parse_ethernet,
    parse_ethernet_auto, parse_profinet, serialize_ethercat,
    serialize_ethernet, serialize_profinet,
)

wire_protocols = [
    "modbus-tcp", "modbus-rtu", "can", "ethernet", "profinet", "ethercat",
]
wireProtocols = wire_protocols


def unsupported(protocol):
    return FieldbridgeError("UNSUPPORTED_FEATURE",
                            f"No wire format is implemented for {protocol} yet",
                            protocol=protocol)


def parse(protocol, input, options=None):
    assert_protocol(protocol)
    options = options or {}
    if protocol == "modbus-tcp":
        result = parse_modbus_tcp_stream(input)
        if result["rest"]:
            raise FieldbridgeError("INVALID_FRAME",
                                   f"modbus-tcp input ends with {len(result['rest'])} bytes "
                                   "of an incomplete ADU",
                                   protocol=protocol)
        return result["frames"]
    if protocol == "modbus-rtu":
        return [parse_modbus_rtu(input)]
    if protocol == "can":
        if isinstance(options, dict):
            return [parse_socket_can(input, options)]
        return [parse_socket_can(input)]
    if protocol == "ethernet":
        return [parse_ethernet(input)]
    if protocol == "profinet":
        return [parse_profinet(input)]
    if protocol == "ethercat":
        return parse_ethercat(input)
    raise unsupported(protocol)


def serialize(frame, options=None):
    if frame is None or not hasattr(frame, "get"):
        raise FieldbridgeError("INVALID_FRAME", "frame must be an object")
    assert_protocol(frame.get("protocol"))
    options = options or {}
    protocol = frame["protocol"]
    if protocol == "modbus-tcp":
        return serialize_modbus_tcp(frame)
    if protocol == "modbus-rtu":
        return serialize_modbus_rtu(frame)
    if protocol == "can":
        return serialize_socket_can(frame, options)
    if protocol == "ethernet":
        return serialize_ethernet(frame)
    if protocol == "profinet":
        return serialize_profinet(frame)
    if protocol == "ethercat":
        if isinstance(options, dict):
            return serialize_ethercat([frame], destination=options.get("destination"),
                                      source=options.get("source"))
        return serialize_ethercat([frame])
    raise unsupported(protocol)


# Names matching the TypeScript API and Python-style aliases
crc16Modbus = crc16_modbus
parseModbusRtu = parse_modbus_rtu
parseModbusTcp = parse_modbus_tcp
parseModbusTcpStream = parse_modbus_tcp_stream
serializeModbusRtu = serialize_modbus_rtu
serializeModbusTcp = serialize_modbus_tcp
parseSocketCan = parse_socket_can
serializeSocketCan = serialize_socket_can
parseCandumpLine = parse_candump_line
formatCandumpLine = format_candump_line
parseEthercat = parse_ethercat
parseEthernet = parse_ethernet
parseEthernetAuto = parse_ethernet_auto
parseProfinet = parse_profinet
serializeEthercat = serialize_ethercat
serializeEthernet = serialize_ethernet
serializeProfinet = serialize_profinet
