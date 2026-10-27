from ..ops import Op, Param

OPS = [
    Op("contacts", "get", "GET", "/contacts/{id}", False, "contacts:read", "Get a contact",
       path_params=["id"]),
    Op("contacts", "find", "GET", "/contacts/find", False, "contacts:read", "Find a contact by email",
       query=[Param("email", "--email", help="contact email, <email>")]),
    Op("contacts", "create", "POST", "/contacts", True, "contacts:write", "Create a contact",
       body=[
           Param("email", "--email", help="contact email, <email>"),
           Param("identity_id", "--identity-id", help="your own identity id for the contact"),
           Param("name", "--name", help="contact name"),
           Param("phone", "--phone", help="contact phone number"),
       ]),
]
