from django.conf import settings
from rest_framework.settings import perform_import
from django.utils.module_loading import import_string

ABDM_AUTH_CLASS = import_string(settings.ABDM_AUTH_CLASS)
