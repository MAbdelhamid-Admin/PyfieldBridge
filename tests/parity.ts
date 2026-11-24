import {
  convertFrame,
  convertMessage,
  createAdapter,
  createConverter,
  tryConvertFrame,
  tryConvertMessage,
} from "../../typescript_fieldbridge/src/index.js";
import {
  CAN_MTU,
  CANFD_MTU,
  crc16Modbus,
  formatCandumpLine,
  parseCandumpLine,
  parseEthercat,
  parseEthernet,
  parseModbusRtu,
  parseModbusTcp,
  parseModbusTcpStream,
  parseSocketCan,
  serializeEthercat,
  serializeModbusRtu,
  serializeModbusTcp,
  serializeSocketCan,
} from "../../typescript_fieldbridge/src/wire/index.js";

function hex(value: string): Uint8Array {
  return Uint8Array.from(value.match(/../g)!.map((part) => parseInt(part, 16)));
}

function safeFrame(fn: () => unknown): unknown {
  try {
    return { ok: true, value: fn() };
  } catch (error: any) {
    return {
      ok: false,
      error: { code: error.code, protocol: error.protocol, field: error.field },
    };
  }
}

function bytes(value: Uint8Array): string {
  return Buffer.from(value).toString("hex");
}

const cases: Record<string, unknown> = {
  can_to_modbus: convertFrame({
    source: { protocol: "can", identifier: 7, address: 1, payload: [3, 0, 10] },
    targetProtocol: "modbus-rtu",
  }),
  signals: convertFrame({
    source: { protocol: "ethernet", payload: [1], signals: { speed: 42 } },
    targetProtocol: "ethercat",
    options: { mapping: { speed: "velocity", temp: "temperature" } },
  }),
  numeric_device_id: convertMessage({
    source: { deviceId: "0x10", message: { protocol: "lin", identifier: 1, payload: [3, 0] } },
    target: { protocol: "modbus-tcp" },
  }),
  message_address_conflict: convertMessage({
    source: { message: { protocol: "modbus-tcp", address: 9, payload: [3, 0] } },
    target: { protocol: "modbus-rtu", deviceId: 2 },
  }),
  source_context_conflict: convertMessage({
    source: { context: { line: "A", site: "x" }, message: { protocol: "ethernet", payload: [1], metadata: { line: "B" } } },
    target: { protocol: "ethercat" },
  }),
  boolean_metadata_conflict: convertMessage({
    source: { message: { protocol: "ethernet", payload: [1], metadata: { flag: true } } },
    target: { protocol: "profinet", context: { flag: false } },
  }),
  empty_mapping: convertFrame({
    source: { protocol: "ethernet", payload: [1], signals: { speed: 42 } },
    targetProtocol: "ethercat",
    options: { mapping: {} },
  }),
  dropped_fields: convertFrame({
    source: { protocol: "ethernet", sourceAddress: 10, destinationAddress: 20, identifier: 2048, payload: [1, 2, 3] },
    targetProtocol: "can",
  }),
  invalid_device_id: safeFrame(() => convertFrame({
    source: { protocol: "ethernet", payload: [1] },
    targetProtocol: "ethercat",
    options: { targetDeviceId: "gateway-1" },
  })),
  invalid_payload: safeFrame(() => convertFrame({
    source: { protocol: "can", identifier: 1, payload: Array(9).fill(0), metadata: { fd: false } },
    targetProtocol: "lin",
  })),
  try_invalid: (() => {
    const result = tryConvertFrame({
      source: { protocol: "can", identifier: 1, payload: Array(9).fill(0), metadata: { fd: false } },
      targetProtocol: "lin",
    });
    if (result.ok) return result;
    return {
      ok: false,
      error: { code: result.error.code, protocol: result.error.protocol, field: result.error.field },
    };
  })(),
  required_context: (() => {
    const converter = createConverter({
      adapters: { ethercat: createAdapter({ protocol: "ethercat", maxPayload: 1486, requiredContext: ["profile"] }) },
    });
    return safeFrame(() => converter.convertMessage({
      source: { message: { protocol: "can", identifier: 1, payload: [1] } },
      target: { protocol: "ethercat" },
    }));
  })(),
  modbus_rtu: {
    frame: parseModbusRtu(hex("1103006B00037687")),
    bytes: bytes(serializeModbusRtu(parseModbusRtu(hex("1103006B00037687")))),
    crc: crc16Modbus(new TextEncoder().encode("123456789")),
  },
  modbus_tcp_stream: (() => {
    const stream = hex("0001000000061103006B000300020000000611060001000300030000000611");
    const result = parseModbusTcpStream(stream);
    return {
      frames: result.frames,
      rest: bytes(result.rest),
      serialized: bytes(serializeModbusTcp(parseModbusTcp(hex("0001000000061103006B0003")))),
    };
  })(),
  socketcan: (() => {
    const data = new Uint8Array(CAN_MTU);
    new DataView(data.buffer).setUint32(0, 0x123, true);
    data[4] = 3;
    data.set([0xde, 0xad, 0xbe], 8);
    const frame = parseSocketCan(data);
    return { frame, bytes: bytes(serializeSocketCan(frame)) };
  })(),
  candump: (() => {
    const frame = parseCandumpLine("(1436509052.249713) vcan0 123#DEADBEEF");
    return { frame, formatted: formatCandumpLine(frame) };
  })(),
  ethernet: (() => {
    const wire = hex("0102030405060A0B0C0D0E0F08004500001C");
    const frame = parseEthernet(wire);
    return { frame };
  })(),
  ethercat: (() => {
    const datagrams = [
      { protocol: "ethercat" as const, payload: [0, 0], metadata: { command: 1, position: -2, offset: 0x10, ethernetSource: 1 } },
    ];
    const wire = serializeEthercat(datagrams);
    return { frames: parseEthercat(wire), bytes: bytes(wire) };
  })(),
};

console.log(JSON.stringify(cases));
