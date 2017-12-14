from __future__ import absolute_import
from datetime import datetime

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
    def all_adherences(self, episode_id):
        return self.es.filter(
            filters.AND(filters.term('episode_id', episode_id),)
        ).sort('adherence_date', desc=True).run().hits

    @memoized
    def dose_known_adherences(self, episode_id):
        # return sorted adherences, so self.latest_adherence_date can reuse the result of this query
        get_all_adherences = self.all_adherences(episode_id)
        return [case for case in get_all_adherences
                if case.get_case_property('adherence_value') in DOSE_KNOWN_INDICATORS]

    def latest_adherence_date(self, episode_id):
        result = self.dose_known_adherences(episode_id)
        if result:
            # the result is sorted on 'adherence_date'
            latest_date = result[0].get('adherence_date')
            try:
                return datetime.strptime(latest_date, '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(latest_date, '%Y-%m-%dT%H:%M:%S').date()
                except ValueError:
                    raise EnikshayTaskException("Adherence row {} does not or has invalid 'adherence_date'".format(
                        result[0]))
        else:
            return None
