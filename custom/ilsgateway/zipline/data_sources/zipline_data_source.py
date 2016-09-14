from django.shortcuts import get_object_or_404

from corehq.apps.locations.models import SQLLocation
from dimagi.utils.decorators.memoized import memoized


class ZiplineDataSource(object):

    def __init__(self, config):
        self.config = config

    @property
    def domain(self):
        return self.config.domain

    @property
    def start_date(self):
        return self.config.start_date

    @property
    def end_date(self):
        return self.config.end_date

    @property
    def location_id(self):
        return self.config.location_id

    @property
    def statuses(self):
        return self.config.statuses

    @property
    @memoized
    def sql_location(self):
        from custom.ilsgateway.reports import ROOT_LOCATION_TYPE
        if not self.location_id:
            return get_object_or_404(SQLLocation, domain=self.domain, location_type__name=ROOT_LOCATION_TYPE)
        else:
            return get_object_or_404(SQLLocation, domain=self.domain, location_id=self.location_id)

    @property
    def columns(self):
        raise NotImplementedError('Not implemented yet')

    def get_data(self, start, limit):
        raise NotImplementedError('Not implemented yet')

    @property
    def total_count(self):
        raise NotImplementedError('Not implemented yet')
