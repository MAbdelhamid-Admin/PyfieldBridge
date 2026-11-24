from ..core.adapter import create_adapter
from .profibus_pa import profibus_definition

profibus_dp_adapter = create_adapter({"protocol": "profibus-dp", **profibus_definition})
