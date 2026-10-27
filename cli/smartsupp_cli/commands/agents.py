from ..ops import Op, Param

OPS = [
    Op("agents", "list", "GET", "/agents", False, "agents:read", "List agents"),
    Op("agents", "get", "GET", "/agents/{id}", False, "agents:read", "Get an agent",
       path_params=["id"]),
    Op("agents", "update", "PATCH", "/agents/{id}", True, "agents:manage", "Update an agent's status",
       path_params=["id"],
       body=[Param("status", "--status", choices=["online", "offline"], help="agent status")]),
    Op("agents", "ping", "POST", "/agents/{id}/ping", True, "agents:manage",
       "Ping an agent to keep it connected", path_params=["id"]),
]
