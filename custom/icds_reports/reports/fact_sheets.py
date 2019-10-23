from collections import OrderedDict

from dateutil.rrule import rrule, MONTHLY
from django.http.response import Http404
from memoized import memoized

from custom.icds_reports.const import AADHAR_SEEDED_BENEFICIARIES
from custom.icds_reports.sqldata.agg_awc_monthly import AggAWCMonthlyDataSource
from custom.icds_reports.sqldata.agg_ccs_record_monthly import AggCCSRecordMonthlyDataSource
from custom.icds_reports.sqldata.agg_child_health_monthly import AggChildHealthMonthlyDataSource
from custom.icds_reports.sqldata.national_aggregation import NationalAggregationDataSource
from custom.icds_reports.utils import person_is_beneficiary_column, default_age_interval


class FactSheetsReport(object):

    def __init__(self, config=None, loc_level='state', show_test=False, beta=False):
        self.loc_level = loc_level
        self.config = config
        self.show_test = show_test
        self.beta = beta

    @property
    def person_is_beneficiary_column(self):
        return person_is_beneficiary_column(self.beta)

    @property
    def new_table_config(self):
        return [
            {
                'category': 'maternal_and_child_nutrition',
                'title': 'Maternal and Child Nutrition',
                'sections': [
                    {
                        'section_title': 'Nutrition Status of Children',
                        'slug': 'nutrition_status_of_children',
                        'order': 1,
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Weighing Efficiency (Children <5 weighed)',
                                'slug': 'status_weighed',
                                'average': [],
                                'format': 'percent',
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Height measurement efficiency (Children <5 measured)',
                                'slug': 'status_height_efficiency',
                                'average': [],
                                'format': 'percent',
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Total number of unweighed children (0-5 Years)',
                                'slug': 'nutrition_status_unweighed',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0 - 5 years who are '
                                          'severely underweight (weight-for-age)',
                                'slug': 'severely_underweight',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0-5 years who '
                                          'are moderately underweight (weight-for-age)',
                                'slug': 'moderately_underweight',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0-5 years who are at normal weight-for-age',
                                'slug': 'status_normal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with severe acute '
                                    'malnutrition (weight-for-height)'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'wasting_severe',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with moderate acute '
                                    'malnutrition (weight-for-height)'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'wasting_moderate',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with normal '
                                    'weight-for-height'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'wasting_normal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with severe stunting '
                                    '(height-for-age)'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'stunting_severe',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with moderate stunting '
                                    '(height-for-age)'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'stunting_moderate',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from {} with normal '
                                    'height-for-age'.format(default_age_interval(self.beta))
                                ),
                                'slug': 'stunting_normal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Percent of children born in month with low birth weight',
                                'slug': 'low_birth_weight',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'interventions',
                'title': 'Interventions',
                'sections': [
                    {
                        'section_title': 'Nutrition Status of Children',
                        'slug': 'nutrition_status_of_children',
                        'order': 1,
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children 1 year+ who have recieved complete '
                                          'immunization required by age 1.',
                                'slug': 'fully_immunized',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                    {
                        'section_title': 'Nutrition Status of Pregnant Women',
                        'slug': 'nutrition_status_of_pregnant_women',
                        'order': 3,
                        'rows_config': [
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who are anemic',
                                'slug': 'severe_anemic',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women with tetanus completed',
                                'slug': 'tetanus_complete',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who had at least 1 ANC visit by delivery',
                                'slug': 'anc_1',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who had at least 2 ANC visits by delivery',
                                'slug': 'anc_2',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who had at least 3 ANC visits by delivery',
                                'slug': 'anc_3',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who had at least 4 ANC visits by delivery',
                                'slug': 'anc_4',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                    {
                        'section_title': 'AWC Infrastructure',
                        'slug': 'awc_infrastructure',
                        'order': 5,
                        'rows_config': [
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs reported medicine kit',
                                'slug': 'medicine_kits',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs reported weighing scale for infants',
                                'slug': 'baby_weighing_scale',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs reported weighing scale for mother and child',
                                'slug': 'adult_weighing_scale',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                ]
            },
            {
                'category': 'behavior_change',
                'title': 'Behavior Change',
                'sections': [
                    {
                        'section_title': 'Child Feeding Indicators',
                        'slug': 'child_feeding_indicators',
                        'order': 2,
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Percentage of children who were put to the breast within one hour of birth.'
                                ),
                                'slug': 'breastfed_at_birth',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Infants 0-6 months of age who '
                                          'are fed exclusively with breast milk.',
                                'slug': 'exclusively_breastfed',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    "Children between 6 - 8 months given timely introduction to solid, "
                                    "semi-solid or soft food."
                                ),
                                'slug': 'cf_initiation',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months complementary feeding',
                                'slug': 'complementary_feeding',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months consuming at least 4 food groups',
                                'slug': 'diet_diversity',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months consuming adequate food',
                                'slug': 'diet_quantity',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months '
                                          'whose mothers handwash before feeding',
                                'slug': 'handwashing',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                    {
                        'section_title': 'Nutrition Status of Pregnant Women',
                        'slug': 'nutrition_status_of_pregnant_women',
                        'order': 3,
                        "rows_config": [
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Women resting during pregnancy',
                                'slug': 'resting',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Women eating an extra meal during pregnancy',
                                'slug': 'extra_meal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': (
                                    "Pregnant women in 3rd trimester counselled "
                                    "on immediate and exclusive "
                                    "breastfeeding during home visit"
                                ),
                                'slug': 'trimester',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'water_sanitation_and_hygiene',
                'title': 'Water Sanitation And Hygiene',
                "sections": [
                    {
                        'section_title': 'AWC Infrastructure',
                        'slug': 'awc_infrastructure',
                        'order': 5,
                        'rows_config': [
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs reported clean drinking water',
                                'slug': 'clean_water',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs reported functional toilet',
                                'slug': 'functional_toilet',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'demographics',
                'title': 'Demographics',
                'sections': [
                    {
                        'section_title': 'Demographics',
                        'slug': 'demographics',
                        'order': 4,
                        'rows_config': [
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Number of Households',
                                'slug': 'cases_household',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total Number of Household Members',
                                'slug': 'cases_person_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total number of members enrolled at AWC',
                                'slug': self.person_is_beneficiary_column,
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': AADHAR_SEEDED_BENEFICIARIES,
                                'slug': 'aadhar',
                                'format': 'percent',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total pregnant women ',
                                'slug': 'cases_ccs_pregnant_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total pregnant women enrolled for services at AWC',
                                'slug': 'cases_ccs_pregnant',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total lactating women',
                                'slug': 'cases_ccs_lactating_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total lactating women registered for services at AWC',
                                'slug': 'cases_ccs_lactating',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total children (0-6 years)',
                                'slug': 'cases_child_health_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total chldren (0-6 years) enrolled for Anganwadi Services',
                                'slug': 'cases_child_health',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (0-28 days)  enrolled for Anganwadi Services',
                                'slug': 'zero',
                                'average': [],
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (28 days - 6 months)  enrolled for Anganwadi Services',
                                'slug': 'one',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (6 months - 1 year)  enrolled for Anganwadi Services',
                                'slug': 'two',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (1 year - 3 years)  enrolled for Anganwadi Services',
                                'slug': 'three',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (3 years - 6 years)  enrolled for Anganwadi Services',
                                'slug': 'four',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (11-14 years)',
                                'slug': 'cases_person_adolescent_girls_11_14_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (15-18 years)',
                                'slug': 'cases_person_adolescent_girls_15_18_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (11-14 years)  enrolled for Anganwadi Services',
                                'slug': 'cases_person_adolescent_girls_11_14',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (15-18 years)  enrolled for Anganwadi Services',
                                'slug': 'cases_person_adolescent_girls_15_18',
                                'average': [],

                            }
                        ]
                    },
                ]
            }
        ]

    def data_sources(self, config):
        return {
            'AggChildHealthMonthlyDataSource': AggChildHealthMonthlyDataSource(
                config=config,
                loc_level=self.loc_level,
                show_test=self.show_test,
                beta=self.beta
            ),
            'AggCCSRecordMonthlyDataSource': AggCCSRecordMonthlyDataSource(
                config=config,
                loc_level=self.loc_level,
                show_test=self.show_test,
            ),
            'AggAWCMonthlyDataSource': AggAWCMonthlyDataSource(
                config=config,
                loc_level=self.loc_level,
                show_test=self.show_test,
                beta=self.beta
            )
        }

    @memoized
    def get_data_for_national_aggregatation(self, data_source_name):
        national_config = {
            'domain': self.config['domain'],
            'previous_month': self.config['previous_month'],
        }
        return NationalAggregationDataSource(
            national_config,
            self.data_sources(config=national_config)[data_source_name],
            show_test=self.show_test,
            beta=self.beta
        ).get_data()

    def _get_collected_sections(self, config_list):
        sections_by_slug = OrderedDict()
        for config in config_list:
            for section in config['sections']:
                slug = section['slug']
                if slug not in sections_by_slug:
                    sections_by_slug[slug] = {
                        'slug': slug,
                        'section_title': section['section_title'],
                        'order': section['order'],
                        'rows_config': section['rows_config']
                    }
                else:
                    sections_by_slug[slug]['rows_config'].extend(section['rows_config'])
        return sorted(list(sections_by_slug.values()), key=lambda x: x['order'])

    def _get_needed_data_sources(self, config):
        needed_data_sources = set()
        for section in config['sections']:
            for row in section['rows_config']:
                needed_data_sources.add(row['data_source'])
        return needed_data_sources

    def _get_all_data(self, data_sources):
        all_data = []
        first_data_source = data_sources[0]
        for idx in range(0, len(first_data_source)):
            data = first_data_source[idx]
            for other_data_source in data_sources[1:]:
                data.update(other_data_source[idx])
            all_data.append(data)
        return all_data

    @property
    def config_list(self):
        return [
            c for c in self.new_table_config if
            c['category'] == self.config['category'] or self.config['category'] == 'all'
        ]

    def get_data(self):
        config_list = self.config_list
        if not config_list:
            raise Http404()

        if len(config_list) == 1:
            config = config_list[0]
        else:
            config = {
                'title': 'All',
                'sections': self._get_collected_sections(config_list)
            }

        needed_data_sources = self._get_needed_data_sources(config)

        data_sources = [
            data_source.get_data()
            for k, data_source in self.data_sources(self.config).items()
            if k in needed_data_sources
        ]

        all_data = self._get_all_data(data_sources)

        months = [
            dt.strftime("%b %Y") for dt in rrule(
                MONTHLY,
                dtstart=self.config['two_before'],
                until=self.config['month'])
        ]

        for month in months:
            data_for_month = False
            month_data = {}
            for row_data in all_data:
                m = row_data['month'].strftime("%b %Y")
                if month == m:
                    month_data = row_data
                    data_for_month = True

            for section in config['sections']:
                section['months'] = months
                for row in section['rows_config']:
                    if 'data' not in row:
                        row['data'] = [{'html': row['header']}]

                    if data_for_month:
                        row['data'].append((month_data[row['slug']] or {'html': 0}))
                    else:
                        row['data'].append({'html': 0})

                    if 'average' in row:
                        row['average'] = self.get_data_for_national_aggregatation(
                            row['data_source']
                        )[0][row['slug']]

        return {'config': config}
