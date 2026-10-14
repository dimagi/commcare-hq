"""Shared preview and general-release eligibility for CommCare Companion."""

from corehq.apps.domain.models import ChatbotDomainSettings
from corehq.feature_previews import OCS_CHATBOT
from corehq.toggles import NAMESPACE_DOMAIN, GA_OCS_CHATBOT


def chatbot_enabled_for_request(request):
    user = getattr(request, 'couch_user', None)
    if not user:
        return False
    domain = getattr(request, 'domain', None)
    if not domain:
        return False
    if GA_OCS_CHATBOT.enabled(domain, namespace=NAMESPACE_DOMAIN):
        return not ChatbotDomainSettings.objects.filter(domain=domain, disabled=True).exists()
    return OCS_CHATBOT.enabled(domain)
