from ..ops import Op, Param

_FIELDS = [
    Param("name", "--name", help="tag name (1-128 characters)"),
    Param("color", "--color", help="color such as #a1b2c3"),
    Param("description", "--description", help="tooltip description (max 1000 characters)"),
]

OPS = [
    Op("tags", "list", "GET", "/tags", False, "tags:read", "List all tags"),
    Op("tags", "create", "POST", "/tags", True, "tags:write", "Create a tag",
       body=[Param("name", "--name", required=True, help="tag name (1-128 characters)")] + _FIELDS[1:]),
    Op("tags", "update", "PATCH", "/tags/{tag_id}", True, "tags:write", "Update a tag",
       path_params=["tag_id"], body=list(_FIELDS), body_required=True),
    Op("tags", "delete", "DELETE", "/tags/{tag_id}", True, "tags:write", "Delete a tag",
       path_params=["tag_id"]),
]
