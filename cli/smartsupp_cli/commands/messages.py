from ..ops import Op, Param

OPS = [
    Op("messages", "get", "GET", "/messages/{id}", False, "conversations:read", "Get a message",
       path_params=["id"]),
    Op("messages", "find", "GET", "/messages/find", False, "conversations:read",
       "Find a message by its custom id",
       query=[Param("ext_id", "--ext-id", required=True, help="custom message id")]),
]
