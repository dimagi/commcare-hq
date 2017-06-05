from dateutil.parser import parse

from corehq.apps.es import filters
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter

from custom.enikshay.const import DOSE_KNOWN_INDICATORS
from custom.enikshay.exceptions import EnikshayTaskException
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
        # return sorted adherences, so self.latest_adherence_date can reuse the result of this query
        return self.es.filter(self._base_filters(episode_id)).sort('adherence_date', desc=True).run().hits

    def latest_adherence_date(self, episode_id):
        result = self.dose_known_adherences(episode_id)
        if result:
            # the result is sorted on 'adherence_date'
            latest_date = result[0].get('adherence_date')
            parsed_date = parse(latest_date).date()
            if not latest_date or not parsed_date:
                raise EnikshayTaskException("Adherence row {} does not or has invalid 'adherence_date'".format(
                    result[0]))
            else:
                return parsed_date
        else:
            return None
