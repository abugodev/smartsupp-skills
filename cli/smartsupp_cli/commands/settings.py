from ..ops import Op, Param

OPS = [
    Op("settings", "office-hours", "GET", "/settings/office-hours", False, "",
       "Get the office hours settings"),
    Op("settings", "domain-whitelist", "GET", "/settings/domain-whitelist", False, "",
       "Get the whitelisted domain list"),
    Op("settings", "set-domain-whitelist", "PUT", "/settings/domain-whitelist", True, "",
       "Replace the whitelisted domain list",
       body=[Param("allowedDomains", "--domain", required=True, repeat=True,
                   help="allowed domain (repeat the flag for several)")]),
]
