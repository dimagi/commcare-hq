from django.conf import settings

try:
    CASEXML_FORCE_DOMAIN_CHECK = settings.CASEXML_FORCE_DOMAIN_CHECK
except AttributeError:
    CASEXML_FORCE_DOMAIN_CHECK = False