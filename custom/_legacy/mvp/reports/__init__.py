import hashlib
from couchdbkit import ResourceNotFound
from django.core.cache import cache
from django.http import HttpResponse
import json
from corehq.apps.indicators.models import DynamicIndicatorDefinition

from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from mvp.indicator_admin import custom
from mvp.models import MVP


class MVPIndicatorReport(CustomProjectReport, ProjectReportParametersMixin):
    """
        All MVP Reports with indicators should inherit from this.
    """
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter']

    def indicator_cache_key(self, indicator_slug, is_debug=False):
        key = "%(view_slug)s:%(domain)s:%(indicator_slug)s:%(query_string)s%(debug)s" % {
            'view_slug': self.slug,
            'domain': self.domain,
            'indicator_slug': indicator_slug,
            'query_string': self.request.META['QUERY_STRING'],
            'debug': ':DEBUG' if is_debug else '',
        }
        return hashlib.md5(key).hexdigest()

    def get_response_for_indicator(self, indicator):
        raise NotImplementedError

    @property
    def return_cached_data(self):
        return self.request.GET.get('cache', '').lower() == 'true'

    @property
    def is_debug(self):
        return self.request.GET.get('debug', '').lower() == 'true'

    @property
    def partial_response(self):
        indicator_slug = self.request.GET.get('indicator')
        response = {
            'error': True,
            'message': 'Indicator could not be processed.'
        }
        cache_key = self.indicator_cache_key(
            indicator_slug, is_debug=self.is_debug
        )
        cached_data = cache.get(cache_key)
        if cached_data and self.return_cached_data:
            response = cached_data
        elif indicator_slug:
            try:
                indicator = DynamicIndicatorDefinition.get_current(
                    MVP.NAMESPACE,
                    self.domain,
                    indicator_slug,
                    wrap_correctly=True,
                )
                response = self.get_response_for_indicator(indicator)
                if response is not None:
                    cache.set(cache_key, response, 3600)
                else:
                    response = {
                        'error': True,
                        'message': (
                            "This Indicator is currently undergoing updates. "
                            "Please check back shortly."
                        ),
                    }
            except (ResourceNotFound, AttributeError):
                response['message'] = "Indicator '%s' could not be found." % indicator_slug
        return HttpResponse(json.dumps(response), content_type='application/json')


from mvp.reports import mvis, chw, va

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport,
        va.VerbalAutopsyReport,
    )),
)

INDICATOR_ADMIN_INTERFACES = (
    ('MVP Custom Indicators', (
       custom.MVPDaysSinceLastTransmissionAdminInterface,
       custom.MVPActiveCasesAdminInterface,
       custom.MVPChildCasesByAgeAdminInterface,
    )),
)
