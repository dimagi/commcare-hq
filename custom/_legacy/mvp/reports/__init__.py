import hashlib
from couchdbkit import ResourceNotFound
from django.core.cache import cache
from django.http import HttpResponse
import json
from corehq.apps.indicators.models import DynamicIndicatorDefinition

from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from mvp.models import MVP

class MVPIndicatorReport(CustomProjectReport, ProjectReportParametersMixin):
    """
        All MVP Reports with indicators should inherit from this.
    """
    cache_indicators = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter']


    def indicator_cache_key(self, indicator_slug):
        return hashlib.md5("%s:%s:%s:%s" % (self.slug, self.domain, indicator_slug,
                                            self.request.META['QUERY_STRING'])).hexdigest()

    def get_response_for_indicator(self, indicator):
        raise NotImplementedError

    @property
    def partial_response(self):
        indicator_slug = self.request.GET.get('indicator')
        response = {
            'error': True,
            'message': 'Indicator could not be processed.'
        }
        cache_key = self.indicator_cache_key(indicator_slug)
        cached_data = cache.get(cache_key)
        if cached_data and self.cache_indicators:
            response = cached_data
        elif indicator_slug:
            try:
                indicator = DynamicIndicatorDefinition.get_current(MVP.NAMESPACE, self.domain, indicator_slug,
                    wrap_correctly=True)
                response = self.get_response_for_indicator(indicator)
                if response is not None:
                    cache.set(cache_key, response, 3600)
                else:
                    response = {
                        'error': True,
                        'message': 'This Indicator is currently undergoing updates. Please check back shortly.'
                    }
            except (ResourceNotFound, AttributeError):
                response['message'] = "Indicator '%s' could not be found." % indicator_slug
        return HttpResponse(json.dumps(response))
