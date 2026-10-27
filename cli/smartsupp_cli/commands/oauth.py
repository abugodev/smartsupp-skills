from ..ops import Op, Param

OPS = [
    Op("oauth", "access", "POST", "/oauth/access", True, "",
       "Exchange an authorization code for an access token",
       body=[
           Param("client_id", "--client-id", required=True, help="OAuth client id"),
           Param("client_secret", "--client-secret", required=True, help="OAuth client secret"),
           Param("code", "--code", required=True, help="authorization code"),
       ]),
]
