from abdm_integrator.const import HealthInformationType

from corehq.motech.fhir.const import FHIR_VERSION_4_0_1

ABDM_FHIR_VERSION = FHIR_VERSION_4_0_1
SNOMED_CT_SYSTEM = "http://snomed.info/sct"


class ABDMClinicalArtifact:
    """
    Generic Class to hold metadata information for ABDM Clinical Artifacts as defined
    at https://nrces.in/ndhm/fhir/r4/profiles.html. This should be subclassed and required values should
    be updated.
    """
    TEXT = None
    SNOMED_CT_CODE = None
    HI_TYPE = None
    SUBJECT = 'Patient'
    AUTHOR_CHOICES = [
        'Practitioner', 'Organization', 'PractitionerRole', 'Patient', 'Device', 'RelatedPerson'
    ]
    SECTION_ENTRY_CHOICES = []
    # Resources that are possible for this artifact type in the bundle based on data available in HRP
    BUNDLE_ENTRIES = []

    @classmethod
    def coding(cls):
        return [
            {
                'system': SNOMED_CT_SYSTEM,
                'code': cls.SNOMED_CT_CODE,
                'display': cls.TEXT
            }
        ]


class PrescriptionRecord(ABDMClinicalArtifact):
    TEXT = 'Prescription record'
    SNOMED_CT_CODE = '440545006'
    HI_TYPE = HealthInformationType.PRESCRIPTION
    AUTHOR_CHOICES = ['Practitioner', 'Organization']
    SECTION_ENTRY_CHOICES = ['MedicationRequest', 'Binary']
    BUNDLE_ENTRIES = (
        [ABDMClinicalArtifact.SUBJECT]
        + AUTHOR_CHOICES
        + SECTION_ENTRY_CHOICES
        + ['Encounter', 'DocumentReference', 'MedicationStatement', 'Condition']
    )


class FHIRConfigValidationError(Exception):
    pass


class FHIRMissingCasesError(Exception):
    pass


class FHIRConfigErrorMessage:
    HEALTH_INFORMATION_NOT_SUPPORTED = "Health Information type {health_information_type} is not supported"
    MISSING_DATA_DICT_CONFIG = "Missing data dictionary configuration"
    MISSING_CASE = "Missing Case"
    SUBJECT_CONFIG_ABSENT = MISSING_DATA_DICT_CONFIG + ": {subject} for {artifact}. Please contact Admin."
    AUTHOR_CONFIG_ABSENT = MISSING_DATA_DICT_CONFIG + ": Author for {artifact}. Please contact Admin."
    SECTION_ENTRY_CONFIG_ABSENT = MISSING_DATA_DICT_CONFIG + (": Section entry for {artifact}."
                                                              " Please contact Admin.")
    SUBJECT_CASE_ABSENT = MISSING_CASE + ": {subject} for {artifact}"
    AUTHOR_CASE_ABSENT = MISSING_CASE + ": Author for {artifact}"
    SECTION_ENTRY_CASE_ABSENT = MISSING_CASE + ": Section entry for {artifact}"
    DATA_DICT_FHIR_CONFIG = "Data dictionary configuration error. Please notify admin."


def artifact_from_health_information_type(health_information_type):
    if health_information_type == HealthInformationType.PRESCRIPTION:
        return PrescriptionRecord


def validate_fhir_configuration_for_artifact(clinical_artifact, configured_resource_types):
    if clinical_artifact.SUBJECT not in configured_resource_types:
        raise FHIRConfigValidationError(
            FHIRConfigErrorMessage.SUBJECT_CONFIG_ABSENT.format(
                subject=clinical_artifact.SUBJECT,
                artifact=clinical_artifact
            )
        )
    if not any(
        resource_type in clinical_artifact.AUTHOR_CHOICES for resource_type in configured_resource_types
    ):
        raise FHIRConfigValidationError(
            FHIRConfigErrorMessage.AUTHOR_CONFIG_ABSENT.format(artifact=clinical_artifact)
        )
    if not any(
        resource_type in clinical_artifact.SECTION_ENTRY_CHOICES for resource_type in configured_resource_types
    ):
        raise FHIRConfigValidationError(
            FHIRConfigErrorMessage.AUTHOR_CONFIG_ABSENT.format(artifact=clinical_artifact)
        )


def validate_mandatory_case_types_for_artifact(clinical_artifact, cases_resources_types):
    if clinical_artifact.SUBJECT not in cases_resources_types:
        raise FHIRMissingCasesError(
            FHIRConfigErrorMessage.SUBJECT_CASE_ABSENT.format(
                subject=clinical_artifact.SUBJECT,
                artifact=clinical_artifact
            )
        )
    if not any(resource_type in clinical_artifact.AUTHOR_CHOICES for resource_type in cases_resources_types):
        raise FHIRMissingCasesError(
            FHIRConfigErrorMessage.AUTHOR_CASE_ABSENT.format(artifact=clinical_artifact)
        )
    if not any(
        resource_type in clinical_artifact.SECTION_ENTRY_CHOICES for resource_type in cases_resources_types
    ):
        raise FHIRMissingCasesError(
            FHIRConfigErrorMessage.SECTION_ENTRY_CASE_ABSENT.format(artifact=clinical_artifact)
        )
