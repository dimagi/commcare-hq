from datetime import date
from custom.icds_reports.utils import ICDSMixin
from custom.icds_reports.models.aggregate import AggAwc
from custom.icds_reports.utils import get_location_filter


class BasePopulation(ICDSMixin):

    slug = 'population'

    def __init__(self, config, allow_conditional_agg=False):
        super(BasePopulation, self).__init__(config, allow_conditional_agg)
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


class BasePopulationBeta(ICDSMixin):

    slug = 'population'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        if self.config['location_id']:
            filters = get_location_filter(self.config['location_id'], self.config['domain'])

            if filters.get('aggregation_level')>1:
                filters['aggregation_level'] -= 1

            filters['month'] = date(self.config['year'], self.config['month'], 1)
            print(filters)
            awc_data = AggAwc.objects.filter(**filters).values('cases_person').order_by('month').first()
            return [
                [
                    "Total Population of the project:",
                    awc_data.cases.person if awc_data else 0
                ]
            ]
