"""Reference components for capability-aware agent plan caching."""

from .demand_signature import demand_for_request, extract_demand_record
from .supply_changes import supply_delta
from .impact import assess_plan_impact

__all__ = ["demand_for_request", "extract_demand_record", "supply_delta", "assess_plan_impact"]
