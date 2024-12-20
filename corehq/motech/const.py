from django.utils.translation import gettext_lazy as _

import attr

BASIC_AUTH = "basic"
DIGEST_AUTH = "digest"
OAUTH1 = "oauth1"
BEARER_AUTH = "bearer"
APIKEY_AUTH = "api_key"
OAUTH2_PWD = "oauth2_pwd"
OAUTH2_CLIENT = "oauth2_client"
AUTH_TYPES = (
    (BASIC_AUTH, "HTTP Basic"),
    (DIGEST_AUTH, "HTTP Digest"),
    (OAUTH1, "OAuth1"),

    # https://oauth.net/2/grant-types/client-credentials/
    # https://www.rfc-editor.org/rfc/rfc6749#section-4.4
    (OAUTH2_CLIENT, "OAuth 2.0 Client Credentials Grant"),

    # aka "Resource Owner Password Credentials" grant type
    # Considered legacy
    # > ... should only be used when ... other authorization grant types
    # > are not available
    # https://oauth.net/2/grant-types/password/
    # https://www.rfc-editor.org/rfc/rfc6749#section-1.3.3
    (OAUTH2_PWD, "OAuth 2.0 Password Grant"),

    # This is not a grant type / authentication flow. It is a type of
    # access token. HQ implements this option by requesting a new token
    # before every API request. Users probably want to choose "OAuth 2.0
    # Client Credentials Grant" instead.
    # https://oauth.net/2/bearer-tokens/
    # https://www.rfc-editor.org/rfc/rfc6750
    (BEARER_AUTH, "Bearer Token"),

    # Simple auth scheme that places the key in the request header.
    (APIKEY_AUTH, "API Key"),
)
AUTH_TYPES_REQUIRE_USERNAME = (
    BASIC_AUTH,
    DIGEST_AUTH,
    BEARER_AUTH,
    OAUTH2_PWD,
)

REQUEST_DELETE = "DELETE"
REQUEST_POST = "POST"
REQUEST_PUT = "PUT"
REQUEST_GET = "GET"
DEFAULT_REQUEST_METHODS = (REQUEST_DELETE, REQUEST_POST, REQUEST_PUT)
ALL_REQUEST_METHODS = (REQUEST_DELETE, REQUEST_POST, REQUEST_PUT, REQUEST_GET)


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class OAuth2ApiSettings:
    """
    Settings and endpoints for an OAuth 2.0 API
    """
    # Pass credentials in Basic Auth header when requesting a token?
    # Otherwise they are passed in the request body.
    pass_credentials_in_header: bool
    # Endpoint to fetch bearer token. e.g. '/uaa/oauth/token' (DHIS2)
    token_endpoint: str
    # Endpoint to refresh bearer token. e.g. '/uaa/oauth/token'
    refresh_endpoint: str
    # Name to show in the UI
    friendly_name: str


AUTH_PRESETS = {
    'dhis2_auth_settings': OAuth2ApiSettings(
        friendly_name='DHIS2 OAuth 2.0',
        token_endpoint="/uaa/oauth/token",
        refresh_endpoint="/uaa/oauth/token",
        pass_credentials_in_header=True,
    ),  # https://docs.dhis2.org/master/en/developer/html/webapi_authentication.html
    'moveit_automation_settings': OAuth2ApiSettings(
        friendly_name="MOVEit Automation",
        token_endpoint="/api/v1/token",
        refresh_endpoint="/api/v1/token",
        pass_credentials_in_header=False,
    ),  # https://docs.ipswitch.com/MOVEit/Automation2018/API/REST-API/index.html
}

PASSWORD_PLACEHOLDER = '*' * 16

CONNECT_TIMEOUT = 60
# If any remote service does not respond within 5 minutes, time out.
# (Some OpenMRS reports can take a long time. Cut them a little slack,
# but not too much.)
READ_TIMEOUT = 5 * 60
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

ALGO_AES = 'aes'
ALGO_AES_CBC = 'aes-cbc'


IMPORT_FREQUENCY_DAILY = 'daily'
IMPORT_FREQUENCY_WEEKLY = 'weekly'
IMPORT_FREQUENCY_MONTHLY = 'monthly'
IMPORT_FREQUENCY_CHOICES = (
    (IMPORT_FREQUENCY_DAILY, _('Daily')),
    (IMPORT_FREQUENCY_WEEKLY, _('Weekly')),
    (IMPORT_FREQUENCY_MONTHLY, _('Monthly')),
)

DATA_TYPE_UNKNOWN = None

COMMCARE_DATA_TYPE_TEXT = 'cc_text'
COMMCARE_DATA_TYPE_INTEGER = 'cc_integer'
COMMCARE_DATA_TYPE_DECIMAL = 'cc_decimal'
COMMCARE_DATA_TYPE_BOOLEAN = 'cc_boolean'
COMMCARE_DATA_TYPE_DATE = 'cc_date'
COMMCARE_DATA_TYPE_DATETIME = 'cc_datetime'
COMMCARE_DATA_TYPE_TIME = 'cc_time'
COMMCARE_DATA_TYPES = (
    COMMCARE_DATA_TYPE_TEXT,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_BOOLEAN,
    COMMCARE_DATA_TYPE_DATE,
    COMMCARE_DATA_TYPE_DATETIME,
    COMMCARE_DATA_TYPE_TIME,
)
COMMCARE_DATA_TYPES_AND_UNKNOWN = COMMCARE_DATA_TYPES + (DATA_TYPE_UNKNOWN,)

DIRECTION_IMPORT = 'in'
DIRECTION_EXPORT = 'out'
DIRECTION_BOTH = None
DIRECTIONS = (
    DIRECTION_IMPORT,
    DIRECTION_EXPORT,
    DIRECTION_BOTH,
)

MAX_REQUEST_LOG_LENGTH = 1024 * 1024
