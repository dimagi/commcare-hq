from __future__ import absolute_import
from sqlagg.columns import CountColumn
from sqlagg.filters import RawFilter

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.enikshay.reports.const import TREATMENT_OUTCOMES
from custom.enikshay.reports.generic import EnikshaySqlData

TABLE_ID = 'episode'


def pulmonary_microbiological():
    return [RawFilter("disease_classification = 'pulmonary' AND basis_of_diagnosis = 'microbiological'")]


def pulmonary_clinical():
    return [RawFilter("disease_classification = 'pulmonary' AND basis_of_diagnosis = 'clinical'")]


def extra_pulmonary():
    return [RawFilter("disease_classification = 'extra_pulmonary'")]


def previously_treated():
    return [
        RawFilter(
            "patient_type IN ('recurrent', 'treatment_after_failure',"
            " 'treatment_after_lfu', 'other_previously_treated')"
        )
    ]


def recurrent():
    return [
        RawFilter(
            "patient_type = 'recurrent'"
        )
    ]


def treatment_after_failure():
    return [
        RawFilter(
            "patient_type = 'treatment_after_failure'"
        )
    ]


def treatment_after_lfu():
    return [
        RawFilter(
            "patient_type = 'treatment_after_lfu'"
        )
    ]


def other_previously_treated():
    return [
        RawFilter(
            "patient_type = 'other_previously_treated'"
        )
    ]


def generate_for_all_outcomes(slug, filters):
    columns = [
        DatabaseColumn(
            '',
            CountColumn(
                'doc_id',
                filters=filters + [RawFilter("treatment_outcome IS NOT NULL")],
                alias='total_%s' % slug
            )
        )
    ]

    for treatment_outcome in TREATMENT_OUTCOMES:
        columns.append(
            DatabaseColumn(
                '',
                CountColumn(
                    'doc_id',
                    filters=filters + [RawFilter("treatment_outcome = '%s'" % treatment_outcome)],
                    alias='%s_%s' % (slug, treatment_outcome)
                )
            ),
        )
    return columns


class TreatmentOutcomeSqlData(EnikshaySqlData):

    @property
    def date_property(self):
        return 'treatment_initiation_date'

    @property
    def filters(self):
        filters = super(TreatmentOutcomeSqlData, self).filters
        filters.append(RawFilter('episode_type_patient = 1'))
        filters.append(RawFilter("is_enrolled_in_private = 0"))
        return filters

    @property
    def columns(self):
        return (
            generate_for_all_outcomes('new_patients', self.filters + [RawFilter("patient_type = 'new'")]) +
            generate_for_all_outcomes(
                'new_patients_pulmonary_microbiological',
                self.filters + [RawFilter("patient_type = 'new'")] + pulmonary_microbiological()
            ) +
            generate_for_all_outcomes(
                'new_patients_pulmonary_clinical',
                self.filters + [RawFilter("patient_type = 'new'")] + pulmonary_clinical()
            ) +
            generate_for_all_outcomes(
                'new_patients_extra_pulmonary',
                self.filters + [RawFilter("patient_type = 'new'")] + extra_pulmonary()
            ) +
            generate_for_all_outcomes(
                'previously_treated_patients',
                self.filters + previously_treated()
            ) +
            generate_for_all_outcomes(
                'recurrent_patients',
                self.filters + recurrent()
            ) +
            generate_for_all_outcomes(
                'treatment_after_failure_patients',
                self.filters + treatment_after_failure()
            ) +
            generate_for_all_outcomes(
                'treatment_after_lfu_patients',
                self.filters + treatment_after_lfu()
            ) +
            generate_for_all_outcomes(
                'other_previously_treated_patients',
                self.filters + [RawFilter("basis_of_diagnosis = 'clinical'")] + other_previously_treated()
            ) +
            generate_for_all_outcomes(
                'hiv_reactive_patients',
                self.filters + [RawFilter("hiv_status = 'reactive'")]
            ) +
            generate_for_all_outcomes(
                'new_hiv_reactive_patients',
                self.filters + [RawFilter("patient_type = 'new'")] + [RawFilter("hiv_status = 'reactive'")]
            ) +
            generate_for_all_outcomes(
                'previously_treated_hiv_reactive_patients',
                self.filters + previously_treated() + [RawFilter("hiv_status = 'reactive'")]
            ) + [
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=self.filters + [RawFilter("hiv_status = 'reactive'")],
                        alias='total_hiv_cases'
                    )
                )
            ] + [
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=(
                            self.filters + [RawFilter("hiv_status = 'reactive'")] +
                            [RawFilter("initiated_on_art = 'yes'")]
                        ),
                        alias='total_initiated_on_art'
                    )
                )
            ] + [
                DatabaseColumn(
                    '',
                    CountColumn(
                        'doc_id',
                        filters=(
                            self.filters + [RawFilter("hiv_status = 'reactive'")] +
                            [RawFilter("cpt_initiated = 'yes'")]
                        ),
                        alias='total_cpt_initiated'
                    )
                )
            ]
        )
