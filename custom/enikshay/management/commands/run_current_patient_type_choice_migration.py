from __future__ import absolute_import
from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration
from custom.enikshay.nikshay_datamigration.models import PatientDetail

CURRENT_PATIENT_TYPE = 'current_patient_type_choice'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_current_patient_type_choice'


class Command(BaseEnikshayCaseMigration):
    case_type = 'person'
    case_properties_to_update = [
        CURRENT_PATIENT_TYPE,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(person, domain):
        if (
            person.get_case_property(DATAMIGRATION_CASE_PROPERTY) == 'yes'
            or person.get_case_property('migration_created_case') != 'true'
        ):
            return {}

        preg_id = person.get_case_property('migration_created_from_record')
        try:
            patient_detail = PatientDetail.objects.get(PregId=preg_id)
        except PatientDetail.DoesNotExist:
            return {}

        if (
            patient_detail.deprecated_patient_type_choice == person.get_case_property(CURRENT_PATIENT_TYPE)
            and patient_detail.deprecated_patient_type_choice != patient_detail.patient_type_choice
        ):
            return {
                CURRENT_PATIENT_TYPE: patient_detail.patient_type_choice,
            }
        else:
            return {}
