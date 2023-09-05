from corehq.motech.fhir.const import FHIR_VERSION_4_0_1
from custom.abdm.const import HealthInformationType

ABDM_FHIR_VERSION = FHIR_VERSION_4_0_1
SNOMED_CT_SYSTEM = "http://snomed.info/sct"

# IMP TODO CHECK if we can use Data Dict for Composition
# TODO Check if we can generate json schema for ABDM Profiles
# TODO Define other Clinical Artefacts (will require basic testing)
# TODO Refactoring

class ABDMClinicalArtifact:
    """
    Generic Class for ABDM Clinical Artifacts defined https://nrces.in/ndhm/fhir/r4/profiles.html
    based on FHIR Version r4
    """
    SUBJECT_RESOURCE = 'Patient'
    # any of the choice is valid for author
    AUTHOR_RESOURCE_CHOICES = ['Practitioner', 'Organization', 'PractitionerRole',
                               'Patient', 'Device', 'RelatedPerson']
    # Set below attributes for each artifact
    TEXT = None
    SNOMED_CT_CODE = None
    HI_TYPE = None
    # any of the choice is valid for section
    SECTION_ENTRY_RESOURCE_CHOICES = []
    CODING = []


class PrescriptionRecord(ABDMClinicalArtifact):
    TEXT = 'Prescription record'
    SNOMED_CT_CODE = "440545006"
    HI_TYPE = HealthInformationType.PRESCRIPTION
    SECTION_ENTRY_RESOURCE_CHOICES = ['MedicationRequest', 'Binary']
    CODING = [
        {
          "system": SNOMED_CT_SYSTEM,
          "code": SNOMED_CT_CODE,
          "display": TEXT
        }
    ]


def artifact_from_health_information_type(health_information_type):
    if health_information_type == HealthInformationType.PRESCRIPTION:
        return PrescriptionRecord


class FHIRConfigValidationError(Exception):
    pass


def validate_fhir_resources_config(clinical_artifact, resource_types_configured):
    if not (clinical_artifact.SUBJECT_RESOURCE in resource_types_configured):
        raise FHIRConfigValidationError(f"Missing configuration '{clinical_artifact.SUBJECT_RESOURCE}' for subject")
    if not any(resource_type in clinical_artifact.AUTHOR_RESOURCE_CHOICES
               for resource_type in resource_types_configured):
        raise FHIRConfigValidationError(f"Missing configuration for author")
    if not any(resource_type in clinical_artifact.SECTION_ENTRY_RESOURCE_CHOICES
               for resource_type in resource_types_configured):
        raise FHIRConfigValidationError(f"Missing configuration for section entry")
