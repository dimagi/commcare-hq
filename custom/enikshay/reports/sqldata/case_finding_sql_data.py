from sqlagg.columns import CountColumn
from sqlagg.filters import RawFilter

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.enikshay.reports.const import AGE_RANGES
from custom.enikshay.reports.generic import EnikshaySqlData

TABLE_ID = 'episode'


DAYS_IN_YEARS = 365


def generate_for_all_ranges(slug, filters):
    type_filter = RawFilter("patient_type IN ('new', 'recurrent')")
    columns = []
    for lower_bound, upper_bound in AGE_RANGES[:-1]:
        age_filter = RawFilter(
            'age_in_days BETWEEN %d AND %d' % (lower_bound * DAYS_IN_YEARS, upper_bound * DAYS_IN_YEARS)
        )
        columns.append(
            DatabaseColumn(
                '',
                CountColumn(
                    'doc_id',
                    filters=filters + [age_filter, type_filter],
                    alias='%s_age_%d_%d' % (slug, lower_bound, upper_bound)
                )
            )
        )
    columns.append(
        DatabaseColumn(
            '',
            CountColumn(
                'doc_id',
                filters=filters + [
                    RawFilter('age_in_days > %d' % (AGE_RANGES[-1][0] * DAYS_IN_YEARS)), type_filter
                ],
                alias='%s_age_%d' % (slug, AGE_RANGES[-1][0])
            )
        )
    )
    columns.append(
        DatabaseColumn(
            '',
            CountColumn(
                'doc_id',
                filters=filters + [type_filter],
                alias='%s_total' % slug
            )
        )
    )
    return columns


class CaseFindingSqlData(EnikshaySqlData):

    @property
    def columns(self):
        test_type_filter = [
            RawFilter("bacteriological_examination = 1")
        ]

        return (
            generate_for_all_ranges('male', self.filters + [RawFilter("sex = 'male'")]) +
            generate_for_all_ranges('female', self.filters + [RawFilter("sex = 'female'")]) +
            generate_for_all_ranges('transgender', self.filters + [RawFilter("sex = 'transgender'")]) +
            generate_for_all_ranges('all', self.filters) +
            [
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=self.filters + test_type_filter + [RawFilter("episode_type = 'presumptive_tb'")],
                        alias='patients_with_presumptive_tb'
                    )
                ),
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=(
                            self.filters + test_type_filter + [
                                RawFilter("result_of_test = 'tb_detected'"),
                                RawFilter("episode_type = 'presumptive_tb'")
                            ]
                        ),
                        alias='patients_with_positive_tb'
                    )
                ),
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=self.filters + [RawFilter("hiv_status IN ('reactive', 'non_reactive')")],
                        alias='all_hiv_tested'
                    )
                ),
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=self.filters + [RawFilter("hiv_status = 'reactive'")],
                        alias='hiv_reactive'
                    )
                ),
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=self.filters + [RawFilter("hiv_status = 'reactive'")],
                        alias='hiv_reactive_cpt'
                    )
                ),
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=(
                            self.filters + [RawFilter("hiv_status = 'reactive'")] +
                            [RawFilter("initiated_on_art = 'yes'")]
                        ),
                        alias='hiv_reactive_art'
                    )

                )
            ]
        )
