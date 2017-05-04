from django.db import models

from dimagi.utils.decorators.memoized import memoized


def get_agency_by_motech_user_name(motech_user_name):
    try:
        return Agency.objects.get(
            agencyId=UserDetail.objects.get(
                motechUserName=motech_user_name
            ).agencyId
        )
    except (Agency.DoesNotExist, UserDetail.DoesNotExist):
        return None


class Beneficiary(models.Model):
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
    firstName = models.CharField(max_length=30, null=True)
    gender = models.CharField(max_length=10, null=True)
    identificationNumber = models.CharField(max_length=30, null=True)
    identificationTypeId = models.CharField(max_length=10, null=True)
    isActive = models.CharField(max_length=10, null=True)
    languagePreferences = models.CharField(max_length=30, null=True)
    lastName = models.CharField(max_length=30, null=True)
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
    phoneNumber = models.CharField(max_length=10, null=True)
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
    def referred_provider(self):
        return get_agency_by_motech_user_name(self.referredQP)

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
        }[self.identificationTypeId]


class Episode(models.Model):
    id = models.IntegerField(null=True)
    accountName = models.CharField(max_length=255, null=True)
    accountType = models.CharField(max_length=255, null=True)
    adherenceScore = models.DecimalField(decimal_places=10, max_digits=14)
    alertFrequencyId = models.IntegerField()
    associatedFO = models.CharField(max_length=255, null=True)
    bankName = models.CharField(max_length=255, null=True)
    basisOfDiagnosis = models.CharField(max_length=255, null=True)
    beneficiaryID = models.ForeignKey(Beneficiary, on_delete=models.CASCADE)
    branchName = models.CharField(max_length=255, null=True)
    creationDate = models.DateTimeField(null=True)
    creator = models.CharField(max_length=255, null=True)
    dateOfDiagnosis = models.DateTimeField(null=True)
    diabetes = models.CharField(max_length=255, null=True)
    dstStatus = models.CharField(max_length=255, null=True)
    episodeDisplayID = models.IntegerField()
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
    rxStartDate = models.DateTimeField(null=True)
    rxSupervisor = models.CharField(max_length=255, null=True)
    site = models.CharField(max_length=255, null=True)
    status = models.CharField(max_length=255, null=True)
    treatingQP = models.CharField(max_length=255, null=True)
    treatmentOutcomeId = models.CharField(max_length=255, null=True)
    treatmentPhase = models.CharField(max_length=255, null=True)
    # [u'Select',
    #  None,
    #  u'Intensive Phase',
    #  u'N/A',
    #  u'Continuation Phase',
    #  u'Extended IP']
    tsProviderType = models.CharField(max_length=255, null=True)
    unknownAdherencePct = models.DecimalField(decimal_places=10, max_digits=14)
    unresolvedMissedDosesPct = models.DecimalField(decimal_places=10, max_digits=14)
    treatingHospital = models.CharField(max_length=10, null=True)
    treatmentCompletionInsentiveFlag = models.CharField(max_length=1, null=True)
    mermIMIEno = models.CharField(max_length=255, null=True)
    adherenceSupportAssigned = models.CharField(max_length=255, null=True)

    @property
    def current_patient_type_choice(self):
        if self.newOrRetreatment == 'New':
            return 'new'
        elif self.newOrRetreatment == 'Retreatment':
            if self.retreatmentReason in ['Recurrent', 'Relapse']:
                return 'recurrent'
            elif self.retreatmentReason == 'After Treatment Failure':
                return 'treatment_after_failure'
            elif self.retreatmentReason == 'After loss to follow-up':
                return 'treatment_after_lfu'
            elif self.retreatmentReason == 'Others':
                return 'other_previously_treated'
        return ''  # TODO - handle

    @property
    def diabetes_status(self):
        return {
            'Yes': 'diabetic',
            'No': 'non-diabetic',
            'Not known': 'unknown',
            None: 'unknown',
            'Select': 'unknown',
        }[self.diabetes]

    @property
    def disease_classification(self):
        return {
            'Pulmonary': 'pulmonary',
            'Extrapulmonary': 'extra_pulmonary',
            'Pulmonary+Extrapulmonary': 'extra_pulmonary',
            'Select': '',
            'N/A': '',
        }[self.site]

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
    def site_choice(self):
        return {
            'Abdomen': 'abdominal',
            'Bones And Joints': 'other',
            'Brain': 'brain',
            'Eye': 'other',
            'Genitourinary': 'other',
            'Intestines': 'other',
            'Lymph Nodes': 'lymph_node',
            'Other': 'other',
            'Pleural effusion': 'pleural_effusion',
            'Skin': 'other',
            'Spine': 'spine',
            None: '',
            'Select': '',
        }[self.extraPulmonary]

    @property
    def treating_provider(self):
        return get_agency_by_motech_user_name(self.treatingQP)

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
                'died': 'died',
                'Failure': 'failure',
                'SWITCH TO CAT IV': 'regimen_changed',
                'Switched to Category IV/V': 'regimen_changed',
            }[self.treatmentOutcomeId]

    @property
    def is_treatment_ended(self):
        return self.treatment_outcome in [
            'cured',
            'treatment_complete',
            'died',
            'failure',
            'loss_to_follow_up',
            'regimen_changed',
        ]


class Adherence(models.Model):
    id = models.IntegerField(null=True)
    adherenceId = models.CharField(max_length=18, primary_key=True)
    beneficiaryId = models.ForeignKey(Beneficiary, null=True, on_delete=models.CASCADE)
    commentId = models.CharField(max_length=8, null=True)
    creationDate = models.DateTimeField()
    creator = models.CharField(max_length=255, null=True)
    dosageStatusId = models.IntegerField()
    doseDate = models.DateTimeField()
    doseReasonId = models.IntegerField()
    episodeId = models.ForeignKey(Episode, on_delete=models.CASCADE)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    owner = models.CharField(max_length=255, null=True)
    reportingMechanismId = models.IntegerField()
    unknwDoseReasonId = models.CharField(max_length=8, null=True)

    @property
    def adherence_value(self):
        return {
            0: 'directly_observed_dose',
            1: 'missed_dose',
            3: 'self_administered_dose',
        }[self.dosageStatusId]


class EpisodePrescription(models.Model):
    id = models.BigIntegerField(primary_key=True)
    adultOrPaediatric = models.CharField(max_length=255, null=True)
    beneficiaryId = models.ForeignKey(Beneficiary, null=True, on_delete=models.CASCADE)
    creationDate = models.DateTimeField(null=True)
    creator = models.CharField(max_length=255, null=True)
    dosageStrength = models.CharField(max_length=255, null=True)
    episodeId = models.ForeignKey(Episode, null=True, on_delete=models.CASCADE)
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    next_refill_date = models.DateTimeField(null=True)
    numberOfDays = models.IntegerField()
    numberOfDaysPrescribed = models.CharField(max_length=255, null=True)
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


class LabTest(models.Model):
    id = models.BigIntegerField(primary_key=True)
    cancelledBy = models.CharField(max_length=10, null=True)
    caseId = models.CharField(max_length=18, null=True)
    creationDate = models.DateTimeField(null=True)
    creator = models.CharField(max_length=255, null=True)
    dateOfTest = models.DateTimeField(null=True)
    episodeId = models.ForeignKey(Episode, null=True, on_delete=models.CASCADE)
    labId = models.IntegerField()
    modificationDate = models.DateTimeField(null=True)
    modifiedBy = models.CharField(max_length=255, null=True)
    onBehalfOf = models.CharField(max_length=10, null=True)
    orderedBy = models.CharField(max_length=10, null=True)
    owner = models.CharField(max_length=255, null=True)
    reason = models.CharField(max_length=5, null=True)
    resultDate = models.DateTimeField(null=True)
    # `resultFileContent` mediumblob,
    resultFileFormat = models.CharField(max_length=10, null=True)
    resultFileName = models.CharField(max_length=255, null=True)
    sampleACollectionDate = models.DateTimeField(null=True)
    sampleADeliveryDate = models.DateTimeField(null=True)
    sampleBCollectionDate = models.DateTimeField(null=True)
    sampleBDeliveryDate = models.DateTimeField(null=True)
    sampleCollectionDate = models.DateTimeField(null=True)
    sampleDeliveryDate = models.DateTimeField(null=True)
    tbStatusId = models.IntegerField()
    testId = models.IntegerField()
    testSiteId = models.IntegerField()
    testSiteSpecimenId = models.IntegerField()
    testSpecimenId = models.IntegerField()
    testStatus = models.CharField(max_length=20, null=True)
    treatmentCardId = models.IntegerField()
    treatmentFileId = models.IntegerField()
    voucherNumber = models.IntegerField()
    physicalVoucherNumber = models.CharField(max_length=255, null=True)


class Agency(models.Model):
    id = models.IntegerField(null=True, unique=True)
    agencyId = models.IntegerField(primary_key=True)
    agencyName = models.CharField(max_length=256, null=True)
    agencyStatus = models.CharField(max_length=256, null=True)
    agencySubTypeId = models.CharField(max_length=256, null=True)
    agencyTypeId = models.CharField(max_length=256, null=True)
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
        agency_ids = UserDetail.objects.filter(
            isPrimary=True,
        ).filter(
            stateId=state_id,
            districtId=district_id,
            blockOrHealthPostId=block_id,
            wardId=ward_id,
        ).values('agencyId').distinct()
        return Agency.objects.filter(agencyId__in=agency_ids)

    @property
    def location_type(self):
        return {
            'ATFO': 'pdr',
            'ATHC': 'pac',
            'ATLC': 'plc',
            'ATPH': 'pcc',
            'ATPR': 'pcp',
        }[self.agencyTypeId]

    @property
    def name(self):
        return ' '.join(filter(
            None,
            [
                self._primary_user_detail.firstName,
                self._primary_user_detail.middleName,
                self._primary_user_detail.lastName,
            ]
        ))

    @property
    @memoized
    def _primary_user_detail(self):
        return UserDetail.objects.filter(
            isPrimary=True,
        ).get(agencyId=self.agencyId)


class UserDetail(models.Model):
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
