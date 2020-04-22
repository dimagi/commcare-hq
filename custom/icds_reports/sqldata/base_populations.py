from custom.icds_reports.utils import ICDSMixin


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
            location_id = self.config['location_id']
            month = self.config['month']
            location_type = self.selected_location.location_type.name
            data = AggAwc.objects.get(f'{location_type}_id'=location_id, aggregation_level=self.aggregation_level, month=month).values('cases_person_all')
            return [
                [
                    "Total Population of the project:",
                    data['cases_person_all']
                ]
            ]
