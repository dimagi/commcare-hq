from corehq.apps.sms.mixin import SMSBackend

from django_countries.countries import COUNTRIES
from django.utils.encoding import force_unicode
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE


def get_global_backends_by_class(backend_class):
    return filter(lambda bk: bk.doc_type == backend_class.__name__,
                  SMSBackend.view(
                      'sms/global_backends',
                      reduce=False,
                      include_docs=True,
                  ))


def country_name_from_isd_code_or_empty(isd_code):
    countries = dict(COUNTRIES)
    cc = COUNTRY_CODE_TO_REGION_CODE.get(isd_code)
    return force_unicode(countries.get(cc[0])) if cc else ''
