from corehq.apps.sms.models import Keyword


def get_keywords_for_domain(domain):
    return Keyword.objects.filter(domain=domain)
