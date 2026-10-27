from ..ops import Op

OPS = [
    Op("bots", "trigger", "GET", "/bots/{id}/trigger", False, "bots:read",
       "Get a bot's trigger", path_params=["id"]),
]
