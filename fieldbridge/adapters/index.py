from ..core.types import AttrDict
from .ethernet import ethernet_adapter
from .profinet import profinet_adapter
from .profibus_pa import profibus_pa_adapter
from .profibus_dp import profibus_dp_adapter
from .modbus import modbus_tcp_adapter, modbus_rtu_adapter
from .can import can_adapter
from .lin import lin_adapter
from .flexray import flexray_adapter
from .ethercat import ethercat_adapter


class FrozenRegistry(dict):
    def __init__(self, values):
        dict.__init__(self, values)

    def __setitem__(self, key, value):
        raise TypeError("adapter registry is frozen")

    def update(self, *args, **kwargs):
        raise TypeError("adapter registry is frozen")

    def __delitem__(self, key):
        raise TypeError("adapter registry is frozen")

    def clear(self):
        raise TypeError("adapter registry is frozen")

    def pop(self, key, *args):
        raise TypeError("adapter registry is frozen")

    def popitem(self):
        raise TypeError("adapter registry is frozen")

    def setdefault(self, key, default=None):
        raise TypeError("adapter registry is frozen")

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


adapters = FrozenRegistry({
    "ethernet": ethernet_adapter,
    "profinet": profinet_adapter,
    "profibus-pa": profibus_pa_adapter,
    "profibus-dp": profibus_dp_adapter,
    "modbus-tcp": modbus_tcp_adapter,
    "modbus-rtu": modbus_rtu_adapter,
    "can": can_adapter,
    "lin": lin_adapter,
    "flexray": flexray_adapter,
    "ethercat": ethercat_adapter,
})
