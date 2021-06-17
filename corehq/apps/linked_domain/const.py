from django.utils.translation import ugettext_lazy

from corehq import toggles

MODEL_FLAGS = 'toggles'
MODEL_PREVIEWS = 'previews'
MODEL_FIXTURE = 'fixture'
MODEL_ROLES = 'roles'
MODEL_LOCATION_DATA = 'custom_location_data'
MODEL_PRODUCT_DATA = 'custom_product_data'
MODEL_USER_DATA = 'custom_user_data'
MODEL_CASE_SEARCH = 'case_search_data'
MODEL_APP = 'app'
MODEL_REPORT = 'report'
MODEL_DATA_DICTIONARY = 'data_dictionary'
MODEL_DIALER_SETTINGS = 'dialer_settings'
MODEL_OTP_SETTINGS = 'otp_settings'
MODEL_HMAC_CALLOUT_SETTINGS = 'hmac_callout_settings'
MODEL_KEYWORD = 'keyword'

INDIVIDUAL_DATA_MODELS = [
    (MODEL_APP, ugettext_lazy('Application')),
    (MODEL_FIXTURE, ugettext_lazy('Lookup Table')),
    (MODEL_REPORT, ugettext_lazy('Report')),
    (MODEL_KEYWORD, ugettext_lazy('Keyword')),
]

DOMAIN_LEVEL_DATA_MODELS = [
    (MODEL_USER_DATA, ugettext_lazy('Custom User Data Fields')),
    (MODEL_PRODUCT_DATA, ugettext_lazy('Custom Product Data Fields')),
    (MODEL_LOCATION_DATA, ugettext_lazy('Custom Location Data Fields')),
    (MODEL_ROLES, ugettext_lazy('User Roles')),
    (MODEL_PREVIEWS, ugettext_lazy('Feature Previews')),
]

SUPERUSER_DATA_MODELS = [
    (MODEL_FLAGS, ugettext_lazy('Feature Flags')),
]

FEATURE_FLAG_DATA_MODELS = [
    (MODEL_CASE_SEARCH, ugettext_lazy('Case Search Settings')),
    (MODEL_DATA_DICTIONARY, ugettext_lazy('Data Dictionary')),
    (MODEL_DIALER_SETTINGS, ugettext_lazy('Dialer Settings')),
    (MODEL_OTP_SETTINGS, ugettext_lazy('OTP Pass-through Settings')),
    (MODEL_HMAC_CALLOUT_SETTINGS, ugettext_lazy('Signed Callout')),
]

NON_SUPERUSER_DATA_MODELS = INDIVIDUAL_DATA_MODELS + DOMAIN_LEVEL_DATA_MODELS + FEATURE_FLAG_DATA_MODELS
LINKED_MODELS = INDIVIDUAL_DATA_MODELS + DOMAIN_LEVEL_DATA_MODELS + FEATURE_FLAG_DATA_MODELS + \
    SUPERUSER_DATA_MODELS

LINKED_MODELS_MAP = dict(LINKED_MODELS)

FEATURE_FLAG_DATA_MODEL_TOGGLES = {
    MODEL_CASE_SEARCH: toggles.SYNC_SEARCH_CASE_CLAIM,
    MODEL_DATA_DICTIONARY: toggles.DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS: toggles.WIDGET_DIALER,
    MODEL_OTP_SETTINGS: toggles.GAEN_OTP_SERVER,
    MODEL_HMAC_CALLOUT_SETTINGS: toggles.HMAC_CALLOUT,
}
