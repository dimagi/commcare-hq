from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration
from custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases import DRUG_MAP, get_drtb_type
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

SENSITIVITY = 'sensitivity'
DRTB_TYPE = 'drtb_type'
DRUG_CLASS = 'drug_class'
DRUG_ID = 'drug_id'
CASE_TYPE_DRUG_RESISTANCE = 'drug_resistance'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_pmdt_drtb_type'


class Command(BaseEnikshayCaseMigration):
    case_type = 'occurrence'
    case_properties_to_update = [
        DRTB_TYPE,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(case, domain):
        if (
            case.get_case_property(DATAMIGRATION_CASE_PROPERTY) == 'yes'
            or case.get_case_property('migration_type') != 'pmdt_excel'
        ):
            return {}

        drug_resistance_cases = _get_drug_resistance_cases(domain, case.case_id)
        drug_resistance_info = [
            {
                DRUG_ID: drug.get_case_property(DRUG_ID),
                SENSITIVITY: drug.get_case_property(SENSITIVITY),
                DRUG_CLASS: DRUG_MAP[drug.get_case_property(DRUG_ID)][DRUG_CLASS],
            }
            for drug in drug_resistance_cases
        ]

        return {
            DRTB_TYPE: get_drtb_type(drug_resistance_info)
        }


def _get_drug_resistance_cases(domain, occurrence_case_id):
    case_accessor = CaseAccessors(domain)
    all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    cases = [case for case in all_cases
             if case.type == CASE_TYPE_DRUG_RESISTANCE]
    return cases
