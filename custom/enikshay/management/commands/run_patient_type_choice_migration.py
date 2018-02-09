from __future__ import absolute_import
from custom.enikshay.management.commands.utils import BaseEnikshayCaseMigration
from custom.enikshay.nikshay_datamigration.models import PatientDetail

PATIENT_TYPE_CHOICE = 'patient_type_choice'
DATAMIGRATION_CASE_PROPERTY = 'datamigration_patient_type_choice'
TRANSFER_IN = 'transfer_in'


class Command(BaseEnikshayCaseMigration):
    case_type = 'episode'
    case_properties_to_update = [
        PATIENT_TYPE_CHOICE,
        TRANSFER_IN,
    ]
    datamigration_case_property = DATAMIGRATION_CASE_PROPERTY
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(episode, domain):
        if (
            episode.get_case_property(DATAMIGRATION_CASE_PROPERTY) == 'yes'
            or episode.get_case_property('migration_created_case') != 'true'
        ):
            return {}

        preg_id = (
            episode.get_case_property('migration_created_from_record')
            or episode.get_case_property('nikshay_id')
        )
        try:
            patient_detail = PatientDetail.objects.get(PregId=preg_id)
        except PatientDetail.DoesNotExist:
            return {}

        updates = {}

        if (
            patient_detail.deprecated_patient_type_choice == episode.get_case_property(PATIENT_TYPE_CHOICE)
            and patient_detail.deprecated_patient_type_choice != patient_detail.patient_type_choice
        ):
            updates[PATIENT_TYPE_CHOICE] = patient_detail.patient_type_choice

        deprecated_transfer_in = 'yes' if patient_detail.deprecated_patient_type_choice == 'transfer_in' else ''
        correct_transfer_in = 'yes' if patient_detail.patient_type_choice == 'transfer_in' else 'no'
        if (
            deprecated_transfer_in == episode.get_case_property(TRANSFER_IN)
            and deprecated_transfer_in != correct_transfer_in
        ):
            updates[TRANSFER_IN] = correct_transfer_in

        return updates
