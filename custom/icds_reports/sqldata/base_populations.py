from __future__ import absolute_import
from custom.icds_reports.utils import ICDSMixin


class BasePopulation(ICDSMixin):

    slug = 'population'

    def __init__(self, config):
        super(BasePopulation, self).__init__(config)
        self.config.update(dict(
            location_id=config['location_id']
        ))

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            return [
                [
                    "Total Population of the project:",
                    data['open_count']
                ]
            ]
