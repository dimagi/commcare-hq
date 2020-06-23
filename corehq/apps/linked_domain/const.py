from django.utils.translation import ugettext_lazy

MODEL_FLAGS = 'toggles'
MODELS_ROLES = 'roles'
MODEL_LOCATION_DATA = 'custom_location_data'
MODEL_PRODUCT_DATA = 'custom_product_data'
MODEL_USER_DATA = 'custom_user_data'
MODEL_CASE_SEARCH = 'case_search_data'
MODEL_APP = 'app'
MODEL_REPORT = 'report'

LINKED_MODELS = [
    (MODEL_APP, ugettext_lazy('Application')),
    (MODEL_USER_DATA, ugettext_lazy('Custom User Data Fields')),
    (MODEL_PRODUCT_DATA, ugettext_lazy('Custom Product Data Fields')),
    (MODEL_LOCATION_DATA, ugettext_lazy('Custom Location Data Fields')),
    (MODELS_ROLES, ugettext_lazy('User Roles')),
    (MODEL_FLAGS, ugettext_lazy('Feature Flags and Previews')),
    (MODEL_CASE_SEARCH, ugettext_lazy('Case Search Settings')),
    (MODEL_REPORT, ugettext_lazy('Report')),
]

LINKED_MODELS_MAP = dict(LINKED_MODELS)
