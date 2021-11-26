import attr
from django.utils.translation import ugettext_lazy as _


BASIC_AUTH = "basic"
DIGEST_AUTH = "digest"
OAUTH1 = "oauth1"
BEARER_AUTH = "bearer"
OAUTH2_PWD = "oauth2_pwd"
OAUTH2_CLIENT = "oauth2_client"
AUTH_TYPES = (
    (BASIC_AUTH, "HTTP Basic"),
    (DIGEST_AUTH, "HTTP Digest"),
    (BEARER_AUTH, "Bearer Token"),
    (OAUTH1, "OAuth1"),
    (OAUTH2_PWD, "OAuth 2.0 Password Grant"),
    (OAUTH2_CLIENT, "OAuth 2.0 Client Grant"),
)


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
