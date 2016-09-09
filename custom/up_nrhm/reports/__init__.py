from django.utils.translation import ugettext_noop as _


class LangMixin(object):

    @property
    def lang(self):
        lang = self.request.GET.get('lang', 'en')
        return str(lang) if lang else 'en'

from custom.up_nrhm.reports.asha_reports import ASHAReports

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        ASHAReports,
    )),
)
