from __future__ import absolute_import
from django.db import models

from dimagi.utils.decorators.memoized import memoized

REPORTING_MECHANISM_MISSED_CALL = 83
REPORTING_MECHANISM_99_DOTS = 84
REPORTING_MECHANISM_FIELD_OFFICER = 85
REPORTING_MECHANISM_TREATMENT_SUPPORTER = 86
REPORTING_MECHANISM_TREATMENT_PROVIDER = 87
REPORTING_MECHANISM_PATIENT = 88
REPORTING_MECHANISM_MERM = 96
REPORTING_MECHANISM_AYUSH_OTHER_PROVIDER = 97
REPORTING_MECHANISM_NONE = 0

DIRECTLY_OBSERVED_DOSE = 0
MISSED_DOSE = 1
SELF_ADMINISTERED_DOSE = 3


def get_agency_by_motech_user_name(motech_user_name):
    try:
        return Agency_Jul19.objects.get(
            agencyId=UserDetail_Jul19.objects.get(
                motechUserName=motech_user_name
            ).agencyId
        )
    except (Agency_Jul19.DoesNotExist, UserDetail_Jul19.DoesNotExist):
        return None


class Beneficiary_Jul19(models.Model):
    id = models.IntegerField(null=True)
    additionalDetails = models.CharField(max_length=500, null=True)
    addressLineOne = models.CharField(max_length=256, null=True)
    addressLineTwo = models.CharField(max_length=256, null=True)
    age = models.IntegerField(null=True)
    alertFrequency = models.CharField(max_length=60, null=True)
    associatedFOId = models.CharField(max_length=10, null=True)
    associatedQPId = models.CharField(max_length=10, null=True)
    blockOrHealthPostId = models.CharField(max_length=10, null=True)
    caseCreatedBy = models.CharField(max_length=10, null=True)
    caseId = models.CharField(max_length=18, primary_key=True)
    caseName = models.CharField(max_length=62, null=True)
    caseReferredBy = models.CharField(max_length=18, null=True)
    caseStatus = models.CharField(max_length=20, null=True)
    configureAlert = models.CharField(max_length=5, null=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=255, null=True)
    dateOfIdentification = models.DateTimeField(null=True)
    dateOfRegn = models.DateTimeField()
    diagnosisBasisId = models.IntegerField(null=True)
    districtId = models.CharField(max_length=6, null=True)
    dob = models.DateTimeField(null=True)
    email = models.CharField(max_length=6, null=True)
    emergencyContactNo = models.CharField(max_length=10, null=True)
    extraPulmonarySiteId = models.IntegerField(null=True)
    fatherHusbandName = models.CharField(max_length=60, null=True)
    firstName = models.CharField(max_length=30)
    gender = models.CharField(max_length=10, null=True)
    identificationNumber = models.CharField(max_length=30, null=True)
    identificationTypeId = models.CharField(max_length=10, null=True)
    isActive = models.CharField(max_length=10, null=True)
    languagePreferences = models.CharField(max_length=30, null=True)
    lastName = models.CharField(max_length=30)
    mdrTBSuspected = models.CharField(max_length=30, null=True)
    middleName = models.CharField(max_length=30, null=True)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    nikshayId = models.CharField(max_length=10, null=True)
    occupation = models.CharField(max_length=30, null=True)
    onBehalfOf = models.CharField(max_length=10, null=True)
    organisationId = models.IntegerField()
    owner = models.CharField(max_length=255, null=True)
    patientCategoryId = models.IntegerField(null=True)
    phoneNumber = models.CharField(max_length=10)
    pincode = models.IntegerField(null=True)
    provisionalDiagnosis = models.CharField(max_length=255, null=True)
    qpReferralBy = models.CharField(max_length=10, null=True)
    qpReferralConfirmationStatus = models.CharField(max_length=20, null=True)
    referredQP = models.CharField(max_length=10, null=True)
    rifampicinResistanceId = models.IntegerField(null=True)
    rxPreferences = models.CharField(max_length=255, null=True)
    shiftedToCATIVMdr = models.CharField(max_length=5, null=True)
    siteOfDiseaseId = models.IntegerField(null=True)
    stateId = models.CharField(max_length=10, null=True)
    subOrganizationId = models.IntegerField(null=True)
    symptoms = models.CharField(max_length=255, null=True)
    tbCategoryId = models.IntegerField(null=True)
    testToBeConducted = models.CharField(max_length=255, null=True)
    tsAccountTypeId = models.CharField(max_length=6, null=True)
    tsBankAccNo = models.BigIntegerField(null=True)
    tsBankAccountName = models.CharField(max_length=100, null=True)
    tsBankBranch = models.CharField(max_length=100, null=True)
    tsBankIFSCCode = models.CharField(max_length=11, null=True)
    tsBankMicrCode = models.BigIntegerField(null=True)
    tsBankName = models.CharField(max_length=100, null=True)
    tsId = models.CharField(max_length=10, null=True)
    tsPhoneNo = models.CharField(max_length=10, null=True)
    tsType = models.CharField(max_length=20, null=True)
    tsprovidertype = models.CharField(max_length=30, null=True)
    villageTownCity = models.CharField(max_length=60, null=True)
    wardId = models.CharField(max_length=10, null=True)
    physicalCaseId = models.CharField(max_length=18, null=True)

    @property
    def age_entered(self):
        return self.age

    @property
    @memoized
    def creating_agency(self):
        return get_agency_by_motech_user_name(self.creator)

    @property
    def current_address(self):
        if not self.addressLineOne:
            return self.addressLineTwo or ''
        if not self.addressLineTwo:
            return self.addressLineOne or ''
        return ', '.join([self.addressLineOne, self.addressLineTwo])

    @property
    def current_episode_type(self):
        return {
            'patient': 'confirmed_tb',
            'suspect': 'presumptive_tb',
        }[self.caseStatus.strip()]

    @property
    def episode_name(self):
        return {
            'patient': 'Episode #1: Confirmed TB (Patient)',
            'suspect': 'Episode #1: Suspected TB (Patient)',
        }[self.caseStatus.strip()]

    @property
    def husband_father_name(self):
        return self.fatherHusbandName or ''

    @property
    def language_preference(self):
        return {
            '131': 'en',
            '132': 'hin',
            '133': 'bho',
            '152': 'mar',
            '153': 'guj',
            None: '',
        }[self.languagePreferences]

    @property
    def name(self):
        return ' '.join([self.firstName, self.lastName])

    @property
    @memoized
    def referred_provider(self):
        return get_agency_by_motech_user_name(self.referredQP)

    @property
    def send_alerts(self):
        return {
            'Yes': 'yes',
            'No': 'no',
        }[self.configureAlert]

    @property
    def sex(self):
        return {
            '4': 'male',
            '5': 'female',
            '6': 'transgender',
            None: None,
        }[self.gender]

    @property
    def has_aadhaar_number(self):
        return self.identificationTypeId == '16'

    @property
    def other_id_type(self):
        return {
            '17': 'pan_card',
            '18': 'drivers_license',
            '19': 'ration_card',
            '20': 'voter_card',
            '21': 'none',
            None: 'none',
        }[self.identificationTypeId]


class Episode_Jul19(models.Model):
    id = models.IntegerField(null=True)
    accountName = models.CharField(max_length=255, null=True)
    accountType = models.CharField(max_length=255, null=True)
    adherenceScore = models.DecimalField(decimal_places=10, max_digits=14)
    alertFrequencyId = models.IntegerField()
    associatedFO = models.CharField(max_length=255, null=True)
    bankName = models.CharField(max_length=255, null=True)
    basisOfDiagnosis = models.CharField(max_length=255, null=True)
    beneficiaryID = models.CharField(max_length=18, db_index=True)
    branchName = models.CharField(max_length=255, null=True)
    creationDate = models.DateTimeField(null=True)
    creator = models.CharField(max_length=255, null=True)
    dateOfDiagnosis = models.DateTimeField()
    diabetes = models.CharField(max_length=255, null=True)
    dstStatus = models.CharField(max_length=255, null=True)
    episodeDisplayID = models.IntegerField(db_index=True)
    episodeID = models.CharField(max_length=8, primary_key=True)
    extraPulmonary = models.CharField(max_length=255, null=True)
    hiv = models.CharField(max_length=255, null=True)
    ifscCode = models.CharField(max_length=255, null=True)
    isNonSuperVisor = models.CharField(max_length=255, null=True)
    lastMonthAdherencePct = models.DecimalField(decimal_places=10, max_digits=14)
    lastTwoWeeksAdherencePct = models.DecimalField(decimal_places=10, max_digits=14)
    micr = models.CharField(max_length=255, null=True)
    missedDosesPct = models.DecimalField(decimal_places=10, max_digits=14)
    mobileNumber = models.CharField(max_length=255, null=True)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    name = models.CharField(max_length=255, null=True)
    newOrRetreatment = models.CharField(max_length=255, null=True)
    nikshayBy = models.CharField(max_length=255, null=True)
    nikshayID = models.CharField(max_length=18, null=True)
    nonRxSupervisorName = models.CharField(max_length=255, null=True)
    onBeHalfOf = models.CharField(max_length=10, null=True)
    organisationId = models.CharField(max_length=18, null=True)
    owner = models.CharField(max_length=255, null=True)
    patientWeight = models.DecimalField(decimal_places=10, max_digits=40)
    phoneNumber = models.CharField(max_length=255, null=True)
    retreatmentReason = models.CharField(max_length=255, null=True)
    rxArchivalDate = models.DateTimeField(null=True)
    rxAssignedBy = models.CharField(max_length=255, null=True)
    rxInitiationStatus = models.CharField(max_length=255, null=True)
    # [u'Died before treatment start',
    #  u'Lost to follow up/ unable to capture',
    #  u'On treatment (Program support)',
    #  u'On treatment (public)',
    #  u'On treatment (self)',
    #  u'Patient missing',
    #  u'Pending']
    rxOutcomeDate = models.DateTimeField(null=True)
    rxStartDate = models.DateTimeField()
    rxSupervisor = models.CharField(max_length=255, null=True)
    site = models.CharField(max_length=255)
    status = models.CharField(max_length=255, null=True)
    treatingQP = models.CharField(max_length=255, null=True)
    treatmentOutcomeId = models.CharField(max_length=255, null=True)
    treatmentPhase = models.CharField(max_length=255, null=True)
    tsProviderType = models.CharField(max_length=255, null=True)
    unknownAdherencePct = models.DecimalField(decimal_places=10, max_digits=14)
    unresolvedMissedDosesPct = models.DecimalField(decimal_places=10, max_digits=14)
    treatingHospital = models.CharField(max_length=10, null=True)
    treatmentCompletionInsentiveFlag = models.CharField(max_length=1, null=True)
    mermIMIEno = models.CharField(max_length=255, null=True)
    adherenceSupportAssigned = models.CharField(max_length=255, null=True)

    @property
    def adherence_total_doses_taken(self):
        return Adherence_Jul19.objects.filter(
            episodeId=self.episodeID,
            dosageStatusId__in=[DIRECTLY_OBSERVED_DOSE, SELF_ADMINISTERED_DOSE],
        ).count()

    @property
    @memoized
    def adherence_tracking_mechanism(self):
        reporting_mechanism_values = Adherence_Jul19.objects.filter(
            episodeId=self.episodeID,
        ).exclude(
            reportingMechanismId=REPORTING_MECHANISM_NONE,
        ).values('reportingMechanismId').distinct()

        values = [field_to_value['reportingMechanismId'] for field_to_value in reporting_mechanism_values]

        if reporting_mechanism_values:
            if REPORTING_MECHANISM_99_DOTS in values:
                return '99dots'
            elif REPORTING_MECHANISM_MERM in values:
                return 'merm'
            elif REPORTING_MECHANISM_FIELD_OFFICER in values:
                return 'field_officer'
            elif REPORTING_MECHANISM_TREATMENT_SUPPORTER in values:
                return 'treatment_supporter'
            else:
                return 'contact_centre'
        else:
            return ''

    @property
    def basis_of_diagnosis(self):
        return {
            'Clinical - Chest Xray': 'clinical_chest',
            'Clinical - Other': 'clinical_other',
            'Microbiologically Confirmed - Smear-positive': 'microbiological_smear',
            'Microbiologically Confirmed - Xpert MTB/RIF TB-positive': 'microbiological_cbnaat',
            'Microbiologically Confirmed - Xpert TB-positive': '', # TODO
            'Microbiologically Confirmed - Culture-positive': 'microbiological_culture',
            'Microbiologically Confirmed - PCR (including LPA)': 'microbiological_pcr',
            'Microbiologically Confirmed - PCR(including LPA)': 'microbiological_pcr',
            'Microbiologically Confirmed - Other': 'microbiological_other',
        }[self.basisOfDiagnosis]

    @property
    def case_definition(self):
        if self.basis_of_diagnosis in [
            'clinical_chest',
            'clinical_other',
        ]:
            return 'clinical'
        else:
            return 'microbiological'

    @property
    def patient_type(self):
        return {
            'new': 'new',
            'retreatment': self.retreatment_reason,
            '': '',
        }[self.new_retreatment]

    @property
    def retreatment_reason(self):
        if self.newOrRetreatment == 'Retreatment':
            return {
                'After loss to follow-up': 'treatment_after_lfu',
                'After Treatment Failure': 'treatment_after_failure',
                'Recurrent': 'recurrent',
                'Relapse': 'recurrent',
                'Others': '',
                'Select': '',
                None: '',
            }[self.retreatmentReason]
        return ''

    @property
    def diabetes_status(self):
        return {
            'Yes': 'diabetic',
            'No': 'non_diabetic',
            'Not known': 'unknown',
            None: 'unknown',
            'Select': 'unknown',
        }[self.diabetes]

    @property
    def dots_99_enabled(self):
        return 'true' if self.adherence_tracking_mechanism in ['99dots', 'merm'] else 'false'

    @property
    def site_property(self):
        return {
            'Pulmonary': 'pulmonary',
            'Extrapulmonary': 'extrapulmonary',
            'Pulmonary+Extrapulmonary': 'pulmonary_and_extrapulmonary',
            'Select': 'na',
            'N/A': 'na',
        }[self.site]

    @property
    def disease_classification(self):
        return {
            'na': 'na',
            'extrapulmonary': 'extrapulmonary',
            'pulmonary': 'pulmonary',
            'pulmonary_and_extrapulmonary': 'pulmonary',
        }[self.site_property]

    @property
    def dst_status(self):
        return {
            'DST Not done': 'not_done',
            'Pending': 'pending',
            'Rifampicin Resistant(MDR)': 'rif_resistant',
            'Rifampicin sensitive': 'rif_sensitive',
            'XDR': 'xdr',
        }[self.dstStatus]

    @property
    def hiv_status(self):
        return {
            'Positive': 'reactive',
            'Negative': 'non_reactive',
            'Not known': 'unknown',
            'Select': 'unknown',
            None: 'unknown',
        }[self.hiv]

    @property
    def new_retreatment(self):
        return {
            'New': 'new',
            'Retreatment': 'retreatment',
            'N/A': '',
            'Select': '',
            None: '',
        }[self.newOrRetreatment]

    @property
    def site_choice(self):
        if self.site_property in [
            'extrapulmonary',
            'pulmonary_and_extrapulmonary',
        ]:
            return {
                'Abdomen': 'abdominal',
                'Bones And Joints': 'bones_and_joints',
                'Brain': 'brain',
                'Eye': 'eye',
                'Genitourinary': 'genitourinary',
                'Intestines': 'intestines',
                'Lymph Nodes': 'lymph_node',
                'Other': 'other',
                'Pleural effusion': 'pleural_effusion',
                'Skin': 'skin',
                'Spine': 'spine',
                None: 'other',
                'Select': 'other',
            }[self.extraPulmonary]
        else:
            return ''

    @property
    def treating_provider(self):
        return get_agency_by_motech_user_name(self.treatingQP)

    @property
    def treatment_phase(self):
        return {
            'Intensive Phase': 'ip',
            'Extended IP': 'extended_ip',
            'Continuation Phase': 'continuation_phase_cp',
            'N/A': '',
            'Select': '',
            None: '',
        }[self.treatmentPhase]

    @property
    def treatment_outcome(self):
        if self.treatmentOutcomeId is None:
            return None
        elif self.treatmentOutcomeId.startswith('Lost to follow-up'):
            return 'loss_to_follow_up'
        else:
            return {
                'Cured': 'cured',
                'Died': 'died',
                'DIED': 'died',
                'Failure': 'failure',
                'SWITCH OVER CAT4': 'switched_to_cat_ivv',
                'SWITCH TO CAT IV': 'switched_to_cat_ivv',
                'Switched to Category IV/V': 'switched_to_cat_ivv',
                'Transferred Out': 'transferred_out',
                'Treatment Completed': 'treatment_completed',
            }[self.treatmentOutcomeId]

    @property
    def is_treatment_ended(self):
        return self.treatment_outcome in [
            'cured',
            'treatment_complete',
            'died',
            'failure',
            'loss_to_follow_up',
            'switched_to_cat_ivv',
        ]


class Adherence_Jul19(models.Model):
    id = models.IntegerField(null=True)
    adherenceId = models.CharField(max_length=18, primary_key=True)
    beneficiaryId = models.ForeignKey(Beneficiary_Jul19, null=True, on_delete=models.CASCADE)
    commentId = models.CharField(max_length=8, null=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=255, null=True)
    dosageStatusId = models.IntegerField(db_index=True)
    doseDate = models.DateTimeField()
    doseReasonId = models.IntegerField()
    episodeId = models.CharField(max_length=8, db_index=True)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    owner = models.CharField(max_length=255, null=True)
    reportingMechanismId = models.IntegerField(db_index=True)
    unknwDoseReasonId = models.CharField(max_length=8, null=True)

    @property
    def adherence_report_source(self):
        return {
            REPORTING_MECHANISM_MISSED_CALL: 'missed_call',
            REPORTING_MECHANISM_99_DOTS: '',
            REPORTING_MECHANISM_FIELD_OFFICER: 'field_officer',
            REPORTING_MECHANISM_TREATMENT_SUPPORTER: 'treatment_supervisor',
            REPORTING_MECHANISM_TREATMENT_PROVIDER: 'provider',
            REPORTING_MECHANISM_PATIENT: 'patient',
            REPORTING_MECHANISM_MERM: '',
            REPORTING_MECHANISM_AYUSH_OTHER_PROVIDER: 'other',
            REPORTING_MECHANISM_NONE: 'other',
        }[self.reportingMechanismId]

    @property
    def adherence_source(self):
        return {
            REPORTING_MECHANISM_MISSED_CALL: 'enikshay',
            REPORTING_MECHANISM_99_DOTS: '99DOTS',
            REPORTING_MECHANISM_FIELD_OFFICER: 'enikshay',
            REPORTING_MECHANISM_TREATMENT_SUPPORTER: 'enikshay',
            REPORTING_MECHANISM_TREATMENT_PROVIDER: 'enikshay',
            REPORTING_MECHANISM_PATIENT: 'enikshay',
            REPORTING_MECHANISM_MERM: 'MERM',
            REPORTING_MECHANISM_AYUSH_OTHER_PROVIDER: 'enikshay',
            REPORTING_MECHANISM_NONE: 'enikshay',
        }[self.reportingMechanismId]

    @property
    def adherence_value(self):
        return {
            DIRECTLY_OBSERVED_DOSE: 'directly_observed_dose',
            MISSED_DOSE: 'missed_dose',
            SELF_ADMINISTERED_DOSE: 'self_administered_dose',
        }[self.dosageStatusId]


class EpisodePrescription_Jul19(models.Model):
    id = models.BigIntegerField(primary_key=True)
    adultOrPaediatric = models.CharField(max_length=255, null=True)
    beneficiaryId = models.CharField(max_length=18, null=True, db_index=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=255, null=True)
    dosageStrength = models.CharField(max_length=255, null=True)
    episodeId = models.CharField(max_length=8, null=True)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    next_refill_date = models.DateTimeField(null=True)
    numberOfDays = models.IntegerField()
    numberOfDaysPrescribed = models.CharField(max_length=255)
    numberOfRefill = models.CharField(max_length=255, null=True)
    owner = models.CharField(max_length=255, null=True)
    presUnits = models.CharField(max_length=255, null=True)
    prescStatus = models.CharField(max_length=255, null=True)
    prescriptionID = models.IntegerField()
    pricePerUnit = models.DecimalField(decimal_places=10, max_digits=14)
    pricePerUnits = models.CharField(max_length=255, null=True)
    productID = models.IntegerField()
    productName = models.CharField(max_length=255, null=True)
    refill_Index = models.IntegerField()
    typicalUnits = models.CharField(max_length=255, null=True)
    unitDesc = models.CharField(max_length=255, null=True)
    voucherID = models.IntegerField()
    voucherStatus = models.CharField(max_length=255, null=True)
    motechUserName = models.CharField(max_length=255, null=True)
    physicalVoucherNumber = models.CharField(max_length=255, null=True)


class Voucher_Jul19(models.Model):
    id = models.BigIntegerField()
    caseId = models.CharField(max_length=18, null=True)
    comments = models.CharField(max_length=512, null=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=255, null=True)
    episodeId = models.CharField(max_length=8, null=True)
    issuedAmount = models.CharField(max_length=255, null=True)
    labId = models.CharField(max_length=255, null=True)
    labTestId = models.CharField(max_length=255, null=True)
    modificationDate = models.DateTimeField()
    modifiedBy = models.CharField(max_length=255, null=True)
    owner = models.CharField(max_length=255, null=True)
    pharmacyId = models.CharField(max_length=255, null=True)
    prescriptionId = models.CharField(max_length=255, null=True)
    validationModeId = models.CharField(max_length=255, null=True)
    voucherAmount = models.CharField(max_length=255, null=True)
    voucherCreatedDate = models.DateTimeField()
    voucherGeneratedBy = models.CharField(max_length=255, null=True)
    voucherLastUpdateDate = models.DateTimeField(null=True)
    voucherNumber = models.BigIntegerField(primary_key=True)
    voucherStatusId = models.CharField(max_length=255, null=True)
    voucherTypeId = models.CharField(max_length=255, null=True)
    agencyName = models.CharField(max_length=255, null=True)
    voucherCancelledDate = models.DateTimeField(null=True)
    voucherExpiredDate = models.DateTimeField(null=True)
    voucherValidatedDate = models.DateTimeField(null=True)
    voucherUsedDate = models.DateTimeField(null=True)
    physicalVoucherNumber = models.CharField(max_length=255, null=True)
    markedUpVoucherAmount = models.CharField(max_length=255, null=True)
    voucherAmountSystem = models.CharField(max_length=255, null=True)


class Agency_Jul19(models.Model):
    id = models.IntegerField(null=True, unique=True)
    agencyId = models.IntegerField(primary_key=True)
    agencyName = models.CharField(max_length=256, null=True)
    agencyStatus = models.CharField(max_length=256, null=True)
    agencySubTypeId = models.CharField(max_length=256, null=True)
    agencyTypeId = models.CharField(max_length=256)
    associatedFOId = models.CharField(max_length=256, null=True)
    attachedToAgency = models.CharField(max_length=256, null=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=256, null=True)
    dateOfRegn = models.DateTimeField()
    labOrLcc = models.CharField(max_length=256, null=True)
    modificationDate = models.DateTimeField()
    modifiedBy = models.CharField(max_length=256, null=True)
    nikshayId = models.CharField(max_length=256, null=True)
    nikshayProcessedFlag = models.CharField(max_length=1, null=True)
    onBehalfOf = models.CharField(max_length=256, null=True)
    organisationId = models.IntegerField()
    owner = models.CharField(max_length=256, null=True)
    parentAgencyId = models.IntegerField()
    parentAgencyType = models.CharField(max_length=256, null=True)
    payToParentAgency = models.CharField(max_length=256, null=True)
    pendingApproval = models.CharField(max_length=256, null=True)
    regnIssueAuthId = models.CharField(max_length=256, null=True)
    regnNumber = models.CharField(max_length=256, null=True)
    sendAlert = models.CharField(max_length=256, null=True)
    subOrganisationId = models.IntegerField()
    tbDrugInStock = models.CharField(max_length=256, null=True)
    tbTests = models.CharField(max_length=256, null=True)
    trainingAttended = models.CharField(max_length=256, null=True)
    tbCorner = models.CharField(max_length=1, null=True)

    @classmethod
    def get_agencies_by_ward(cls, state_id, district_id, block_id, ward_id):
        agency_ids = UserDetail_Jul19.objects.filter(
            isPrimary=True,
        ).filter(
            stateId=state_id,
            districtId=district_id,
            blockOrHealthPostId=block_id,
            wardId=ward_id,
        ).values('agencyId').distinct()
        return Agency_Jul19.objects.filter(agencyId__in=agency_ids)

    @property
    def location_type(self):
        if self.agencyTypeId == 'ATFO':
            return None
        elif self.agencyTypeId == 'ATPR':
            return {
                'PRQP': 'pcp',
                'PRIP': 'pac',
            }[self.agencySubTypeId]
        else:
            return {
                'ATHC': 'pcp',
                'ATLC': 'plc',
                'ATPH': 'pcc',
            }[self.agencyTypeId]

    @property
    def usertype(self):
        if self.agencyTypeId == 'ATFO':
            return 'ps-fieldstaff'
        return {
            'pac': 'pac',
            'pcc': 'pcc-chemist',
            'pcp': 'pcp',
            'plc': 'plc',
        }[self.location_type]

    @property
    def name(self):
        return ' '.join([_f for _f in [
                self._primary_user_detail.firstName,
                self._primary_user_detail.middleName,
                self._primary_user_detail.lastName,
            ] if _f])

    @property
    @memoized
    def _primary_user_detail(self):
        return UserDetail_Jul19.objects.filter(
            isPrimary=True,
        ).get(agencyId=self.agencyId)


class UserDetail_Jul19(models.Model):
    id = models.IntegerField(primary_key=True)
    accountTypeId = models.CharField(max_length=256, null=True)
    addressLineOne = models.CharField(max_length=256, null=True)
    addressLineTwo = models.CharField(max_length=256, null=True)
    agencyId = models.IntegerField()
    alternateMobileNumber = models.CharField(max_length=256, null=True)
    alternateMobileNumber1 = models.CharField(max_length=256, null=True)
    alternateMobileNumber2 = models.CharField(max_length=256, null=True)
    bankAccountName = models.CharField(max_length=256, null=True)
    bankAccountNumber = models.CharField(max_length=256, null=True)
    bankBranch = models.CharField(max_length=256, null=True)
    bankIFSCCode = models.CharField(max_length=256, null=True)
    bankName = models.CharField(max_length=256, null=True)
    blockOrHealthPostId = models.CharField(max_length=256, null=True)
    creationDate = models.DateTimeField(null=True)
    creator = models.CharField(max_length=256, null=True)
    districtId = models.CharField(max_length=256, null=True)
    dob = models.DateTimeField(null=True)
    email = models.CharField(max_length=256, null=True)
    firstName = models.CharField(max_length=256, null=True)
    gender = models.CharField(max_length=256, null=True)
    isPasswordResetFlag = models.NullBooleanField()
    isPrimary = models.BooleanField()
    landLineNumber = models.CharField(max_length=256, null=True)
    lastName = models.CharField(max_length=256, null=True)
    latitude = models.CharField(max_length=256, null=True)
    longitude = models.CharField(max_length=256, null=True)
    micrCode = models.IntegerField(null=True)
    middleName = models.CharField(max_length=256, null=True)
    mobileNumber = models.CharField(max_length=256, null=True)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=256, null=True)
    motechUserName = models.CharField(max_length=256, unique=True)
    organisationId = models.IntegerField()
    owner = models.CharField(max_length=256, null=True)
    passwordResetFlag = models.BooleanField()
    pincode = models.IntegerField()
    stateId = models.CharField(max_length=256, null=True)
    status = models.CharField(max_length=256, null=True)
    subOrganisationId = models.IntegerField()
    tuId = models.CharField(max_length=256, null=True)
    uniqIDNo = models.CharField(max_length=256, null=True)
    uniqIDType = models.CharField(max_length=256, null=True)
    userId = models.IntegerField()
    userName = models.CharField(max_length=256, null=True)
    valid = models.BooleanField()
    villageTownCity = models.CharField(max_length=256, null=True)
    wardId = models.CharField(max_length=256, null=True)
