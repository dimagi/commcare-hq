from __future__ import absolute_import
from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration

TREATMENT_REGIMEN = 'treatment_regimen'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_pmdt_treatment_regimen'


class Command(BaseEnikshayCaseMigration):
    case_type = 'episode'
    case_properties_to_update = [
        TREATMENT_REGIMEN,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(episode, domain):
        if (
            episode.get_case_property(DATAMIGRATION_CASE_PROPERTY) != 'yes'
            and episode.get_case_property('migration_type') == 'pmdt_excel'
            and episode.get_case_property(TREATMENT_REGIMEN) == 'new_drug_xdr'
        ):
            return {TREATMENT_REGIMEN: 'new_xdr'}
        else:
            return {}
