from django.utils.translation import gettext_lazy

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
MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS = 'tableau_server_and_visualizations'
MODEL_AUTO_UPDATE_RULES = 'auto_update_rules'
MODEL_AUTO_UPDATE_RULE = 'auto_update_rule'
MODEL_UCR_EXPRESSION = 'ucr_expression'

INDIVIDUAL_DATA_MODELS = [
    (MODEL_APP, gettext_lazy('Application')),
    (MODEL_FIXTURE, gettext_lazy('Lookup Table')),
    (MODEL_REPORT, gettext_lazy('Report')),
    (MODEL_KEYWORD, gettext_lazy('Keyword')),
    (MODEL_UCR_EXPRESSION, gettext_lazy('Data Expressions and Filters')),
    (MODEL_AUTO_UPDATE_RULE, gettext_lazy("Automatic Update Rule")),
]

DOMAIN_LEVEL_DATA_MODELS = [
    (MODEL_USER_DATA, gettext_lazy('Custom User Data Fields')),
    (MODEL_LOCATION_DATA, gettext_lazy('Custom Location Data Fields')),
    (MODEL_ROLES, gettext_lazy('User Roles')),
    (MODEL_PREVIEWS, gettext_lazy('Feature Previews')),
    (MODEL_AUTO_UPDATE_RULES, gettext_lazy('Automatic Update Rules')),
    (MODEL_DATA_DICTIONARY, gettext_lazy('Data Dictionary')),
]

SUPERUSER_DATA_MODELS = [
    (MODEL_FLAGS, gettext_lazy('Feature Flags')),
]

FEATURE_FLAG_DATA_MODELS = [
    (MODEL_CASE_SEARCH, gettext_lazy('Case Search Settings')),
    (MODEL_DIALER_SETTINGS, gettext_lazy('Dialer Settings')),
    (MODEL_OTP_SETTINGS, gettext_lazy('OTP Pass-through Settings')),
    (MODEL_HMAC_CALLOUT_SETTINGS, gettext_lazy('Signed Callout')),
    (MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS, gettext_lazy('Tableau Server and Visualizations')),
    (MODEL_PRODUCT_DATA, gettext_lazy('Custom Product Data Fields')),
]

ALL_LINKED_MODELS = INDIVIDUAL_DATA_MODELS + DOMAIN_LEVEL_DATA_MODELS + FEATURE_FLAG_DATA_MODELS + \
    SUPERUSER_DATA_MODELS

LINKED_MODELS_MAP = dict(ALL_LINKED_MODELS)

FEATURE_FLAG_DATA_MODEL_TOGGLES = {
    MODEL_CASE_SEARCH: toggles.SYNC_SEARCH_CASE_CLAIM,
    MODEL_DIALER_SETTINGS: toggles.WIDGET_DIALER,
    MODEL_OTP_SETTINGS: toggles.GAEN_OTP_SERVER,
    MODEL_HMAC_CALLOUT_SETTINGS: toggles.HMAC_CALLOUT,
    MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS: toggles.EMBEDDED_TABLEAU,
    MODEL_PRODUCT_DATA: toggles.COMMTRACK,
}
