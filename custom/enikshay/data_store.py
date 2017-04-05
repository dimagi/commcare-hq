import pytz
from django.utils.dateparse import parse_datetime

from corehq.apps.es import filters
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter

from custom.enikshay.const import DOSE_KNOWN_INDICATORS
from dimagi.utils.decorators.memoized import memoized


class AdherenceDatastore(object):
    # collection of adherence-data lookup queries that can be run on adherence UCR
    def __init__(self, domain):
        self.datasource = StaticDataSourceConfiguration.by_id("static-{}-adherence".format(domain))
        self.adapter = get_indicator_adapter(self.datasource)
        self.es = self.adapter.get_query_object().es

    def _base_filters(self, episode_id):
        return filters.AND(
            filters.term('episode_id', episode_id),
            filters.term('adherence_value', DOSE_KNOWN_INDICATORS)
        )

    @memoized
    def dose_known_adherences(self, episode_id):
        return self.es.filter(self._base_filters(episode_id)).run().hits

    def latest_adherence_date(self, episode_id):
        result = self.dose_known_adherences(episode_id)
        if len(result) > 0:
            latest = sorted(result, key=lambda x: x['adherence_date'])[-1]
            return pytz.UTC.localize(parse_datetime(latest.get('adherence_date')))
        else:
            return None
