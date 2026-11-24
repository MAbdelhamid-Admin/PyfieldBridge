from fieldbridge.wire import (
    CAN_MTU,
    CANFD_MTU,
    EthercatCommand,
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


def test_modbus_reference_and_crc():
    rtu = bytes.fromhex("11 03 00 6B 00 03 76 87")
    frame = parse_modbus_rtu(rtu)
    assert frame.address == 0x11
    assert frame.payload == [0x03, 0x00, 0x6b, 0x00, 0x03]
    assert serialize_modbus_rtu(frame) == rtu
    assert crc16_modbus(b"123456789") == 0x4b37

    tcp_bytes = bytes.fromhex("00 01 00 00 00 06 11 03 00 6B 00 03")
    tcp = parse_modbus_tcp(tcp_bytes)
    assert tcp.address == 0x11
    assert tcp.metadata.transactionId == 1
    assert serialize_modbus_tcp(tcp) == tcp_bytes


def test_modbus_tcp_stream():
    first = bytes.fromhex("00 01 00 00 00 06 11 03 00 6B 00 03")
    second = bytes.fromhex("00 02 00 00 00 06 11 06 00 01 00 03")
    partial = bytes.fromhex("00 03 00 00 00 06 11")
    result = parse_modbus_tcp_stream(first + second + partial)
    assert [frame.metadata.transactionId for frame in result.frames] == [1, 2]
    assert result.rest == partial


def test_socketcan_and_candump():
    classic = bytearray(CAN_MTU)
    classic[0:4] = (0x123).to_bytes(4, "little")
    classic[4] = 3
    classic[8:11] = bytes([0xde, 0xad, 0xbe])
    frame = parse_socket_can(bytes(classic))
    assert frame.identifier == 0x123
    assert frame.payload == [0xde, 0xad, 0xbe]
    assert serialize_socket_can(frame) == bytes(classic)

    line = "(1436509052.249713) vcan0 123#DEADBEEF"
    can = parse_candump_line(line)
    assert can.payload == [0xde, 0xad, 0xbe, 0xef]
    assert format_candump_line(can) == line


def test_ethernet_and_ethercat():
    dst = 0x010203040506
    src = 0x0a0b0c0d0e0f
    frame = parse_ethernet(bytes.fromhex(
        "01 02 03 04 05 06 0A 0B 0C 0D 0E 0F 08 00 45 00 00 1C"
    ))
    assert frame.destination_address == dst
    assert frame.source_address == src
    assert frame.identifier == 0x0800

    datagrams = [
        {
            "protocol": "ethercat",
            "payload": [0, 0],
            "metadata": {
                "command": EthercatCommand["APRD"],
                "position": -2,
                "offset": 0x10,
                "ethernetSource": 1,
            },
        },
    ]
    wire = serialize_ethercat(datagrams)
    parsed = parse_ethercat(wire)
    assert parsed[0].metadata.position == -2
    assert parsed[0].metadata.offset == 0x10
