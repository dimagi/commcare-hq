import datetime
from django.db import models
from django.conf import settings
from custom.rch.utils import fetch_beneficiaries_records, MOTHER_DATA_TYPE, CHILD_DATA_TYPE

STATE_DISTRICT_MAPPING = {
    '28': [
        '523'
    ]
}


class RCHRecord(models.Model):
    RCH_Primary_Key = None

    Caste = models.CharField(null=True, max_length=255)
    Created_On = models.DateTimeField(null=True)
    District_ID = models.PositiveSmallIntegerField(null=True)
    District_Name = models.CharField(null=True, max_length=255)
    HealthBlock_Name = models.CharField(null=True, max_length=255)
    HealthBlock_ID = models.IntegerField(null=True)
    Taluka_ID = models.IntegerField(null=True)
    Taluka_Name = models.CharField(null=True, max_length=255)
    MDDS_TalukaID = models.IntegerField(null=True)
    MDDS_DistrictID = models.PositiveSmallIntegerField(null=True)
    MDDS_StateID = models.PositiveSmallIntegerField(null=True)
    PHC_Name = models.CharField(null=True, max_length=255)
    PHC_ID = models.IntegerField(null=True)
    Subcentre_Name = models.CharField(null=True, max_length=255)
    MDDS_VillageID = models.IntegerField(null=True)
    Mobile_no = models.BigIntegerField(null=True)
    Religion = models.CharField(null=True, max_length=255)
    State_Name = models.CharField(null=True, max_length=255)
    Landline_no = models.CharField(null=True, max_length=255)
    StateID = models.PositiveSmallIntegerField(null=True)
    Updated_On = models.DateTimeField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @classmethod
    def update_beneficiaries(cls, beneficiary_type, days_before=1):
        date_str = str(datetime.date.fromordinal(datetime.date.today().toordinal() - days_before))
        for state_id in STATE_DISTRICT_MAPPING:
            for district_id in STATE_DISTRICT_MAPPING[state_id]:
                records = fetch_beneficiaries_records(date_str, date_str, state_id, beneficiary_type, district_id)
                for record in records:
                    record_pk = [prop.values()[0] for prop in record if prop.keys()[0] == cls.RCH_Primary_Key][0]
                    results = cls.objects.filter(**{cls.RCH_Primary_Key: record_pk})

                    # convert list of dicts of properties to a single dict
                    dict_of_props = {}
                    for prop in record:
                        if prop.keys()[0] in cls.accepted_fields():
                            dict_of_props[prop.keys()[0]] = prop.values()[0]

                    if results:
                        rch_beneficiary = results[0]
                    else:
                        rch_beneficiary = cls()
                    for prop in dict_of_props:
                        setattr(rch_beneficiary, prop, dict_of_props[prop])
                    rch_beneficiary.sanitize_fields()
                    rch_beneficiary.save()

    @classmethod
    def accepted_fields(cls):
        pass

    def sanitize_fields(self):
        pass


class RCHMother(RCHRecord):
    RCH_Primary_Key = 'Registration_no'

    Registration_no = models.BigIntegerField(null=True)
    Case_no = models.IntegerField(null=True)
    EC_Register_srno = models.IntegerField(null=True)
    Name_wife = models.CharField(null=True, max_length=255)
    Name_husband = models.CharField(null=True, max_length=255)
    Whose_mobile = models.CharField(null=True, max_length=255)
    Wife_current_age = models.PositiveSmallIntegerField(null=True)
    Wife_marry_age = models.PositiveSmallIntegerField(null=True)
    Hus_current_age = models.PositiveSmallIntegerField(null=True)
    Hus_marry_age = models.PositiveSmallIntegerField(null=True)
    Male_child_born = models.PositiveSmallIntegerField(null=True)
    Female_child_born = models.PositiveSmallIntegerField(null=True)
    Male_child_live = models.PositiveSmallIntegerField(null=True)
    Female_child_live = models.PositiveSmallIntegerField(null=True)
    Young_child_gender = models.CharField(null=True, max_length=255)
    Young_child_age_year = models.SmallIntegerField(null=True)
    EC_ANM_Name = models.CharField(null=True, max_length=255)
    EC_ASHA_Name = models.CharField(null=True, max_length=255)
    EC_ANMPhone_No = models.BigIntegerField(null=True)
    EC_ASHAPhone_No = models.BigIntegerField(null=True)
    EC_Registration_Yr = models.SmallIntegerField(null=True)
    PW_Aadhar_No = models.BigIntegerField(null=True)
    PW_AadhaarLinked = models.CharField(null=True, max_length=255)
    PW_Branch_Name = models.CharField(null=True, max_length=255)
    Hus_AadhaarLinked = models.CharField(null=True, max_length=255)
    Economic_Status = models.CharField(null=True, max_length=255)
    Mother_BirthDate = models.DateTimeField(null=True)
    Mother_Age = models.PositiveSmallIntegerField(null=True)
    Mother_ANM_ID = models.IntegerField(null=True)
    Mother_ASHA_ID = models.IntegerField(null=True)
    JSY_Beneficiary = models.CharField(null=True, max_length=255)
    JSY_Payment_Received = models.CharField(null=True, max_length=255)
    Delete_Mother = models.CharField(null=True, max_length=255)
    Entry_Type = models.CharField(null=True, max_length=255)
    LMP_Date = models.DateTimeField(null=True)
    EDD_Date = models.DateTimeField(null=True)
    BloodGroup_Test = models.CharField(null=True, max_length=255)
    LMP_Registration_Yr = models.PositiveSmallIntegerField(null=True)
    Last_Pregnancy_Complication = models.CharField(null=True, max_length=255)
    Last_Pregnancy_outcome = models.CharField(null=True, max_length=255)
    Expected_delivery_place = models.CharField(null=True, max_length=255)
    No_of_times_Pregnant = models.PositiveSmallIntegerField(null=True)
    ANC3 = models.DateTimeField(null=True)
    ANC3_Pregnancy_Week = models.SmallIntegerField(null=True)
    ANC3_Weight = models.FloatField(null=True)
    ANC3_BP_Systolic = models.SmallIntegerField(null=True)
    ANC3_BP_Distolic = models.SmallIntegerField(null=True)
    ANC3_Hb_gm = models.FloatField(null=True)
    TT1 = models.DateTimeField(null=True)
    Maternal_Death = models.SmallIntegerField(null=True)
    Death_Reason = models.CharField(null=True, max_length=255)
    PPMC = models.CharField(null=True, max_length=255)
    Delivery_date = models.DateTimeField(null=True)
    Delivery_Place_Name = models.CharField(null=True, max_length=255)
    Delivery_Conducted_By = models.CharField(null=True, max_length=255)
    Delivery_Type = models.CharField(null=True, max_length=255)
    Delivery_Outcomes = models.SmallIntegerField(null=True)
    Live_Birth = models.SmallIntegerField(null=True)
    Still_Birth = models.SmallIntegerField(null=True)
    Discharge_Date = models.DateTimeField(null=True)
    Delivery_Time = models.TimeField(null=True)
    Discharge_Time = models.TimeField(null=True)
    Delivery_Complication = models.CharField(null=True, max_length=255)
    Infant1_Id = models.BigIntegerField(null=True)
    Infant1_Name = models.CharField(null=True, max_length=255)
    Infant1_Baby_Cried = models.CharField(null=True, max_length=255)
    Infant1_Resucitation_Done = models.CharField(null=True, max_length=255)
    Infant1_Gender = models.CharField(null=True, max_length=255)
    Infant1_Weight = models.FloatField(null=True)
    Infant1_Breast_Feeding = models.CharField(null=True, max_length=255)
    Infant2_Baby_Cried = models.CharField(null=True, max_length=255)
    Infant2_Gender = models.CharField(null=True, max_length=255)
    Subcentre_ID = models.IntegerField(null=True)
    Village_Name = models.CharField(null=True, max_length=255)

    ID_No = models.CharField(null=True, max_length=255)
    PW_Enrollment_No = models.CharField(null=True, max_length=255)
    PW_Enrollment_Time = models.DateTimeField(null=True)
    PW_Bank_Name = models.CharField(null=True, max_length=255)
    PW_IFSC_Code = models.CharField(null=True, max_length=255)
    PW_Account_No = models.CharField(null=True, max_length=255)
    Husband_Enrollment_No = models.CharField(null=True, max_length=255)
    Hus_IFSC_Code = models.CharField(null=True, max_length=255)
    DeletedOn = models.DateTimeField(null=True)
    Blood_Group = models.CharField(null=True, max_length=255)
    ANC1 = models.DateTimeField(null=True)
    ANC1_Pregnancy_Week = models.SmallIntegerField(null=True)
    ANC1_Weight = models.CharField(null=True, max_length=255)
    ANC1_BP_Systolic = models.IntegerField(null=True)
    ANC1_BP_Distolic = models.IntegerField(null=True)
    ANC1_Hb_gm = models.CharField(null=True, max_length=255)
    ANC1_FA_Given = models.IntegerField(null=True)
    ANC1_IFA_Given = models.IntegerField(null=True)
    ANC1_Symptoms_High_Risk = models.CharField(null=True, max_length=255)
    ANC1_Referal_Facility = models.CharField(null=True, max_length=255)
    ANC1_Referal_FacilityName = models.CharField(null=True, max_length=255)
    ANC1_Referal_Date = models.DateTimeField(null=True)
    ANC2 = models.DateTimeField(null=True)
    ANC2_Pregnancy_Week = models.SmallIntegerField(null=True)
    ANC2_Weight = models.CharField(null=True, max_length=255)
    ANC2_BP_Systolic = models.IntegerField(null=True)
    ANC2_BP_Distolic = models.IntegerField(null=True)
    ANC2_Hb_gm = models.CharField(null=True, max_length=255)
    ANC4 = models.DateTimeField(null=True)
    ANC4_Pregnancy_Week = models.SmallIntegerField(null=True)
    ANC4_Weight = models.CharField(null=True, max_length=255)
    ANC4_BP_Systolic = models.IntegerField(null=True)
    ANC4_BP_Distolic = models.IntegerField(null=True)
    ANC4_Hb_gm = models.CharField(null=True, max_length=255)
    TT2 = models.DateTimeField(null=True)
    TTB = models.DateTimeField(null=True)
    AbortionDate = models.DateTimeField(null=True)
    Abortion_Type = models.CharField(null=True, max_length=255)
    Abortion_Preg_Weeks = models.CharField(null=True, max_length=255)
    Induced_Indicate_Facility = models.CharField(null=True, max_length=255)
    Death_Date = models.DateTimeField(null=True)
    Delivery_Place = models.CharField(null=True, max_length=255)
    JSY_Paid_Date = models.DateTimeField(null=True)
    PNC1_Type = models.IntegerField(null=True)
    PNC1_Date = models.DateTimeField(null=True)
    PNC1_IFA_Tab = models.IntegerField(null=True)
    PNC1_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC1_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC1_PPC = models.CharField(null=True, max_length=255)
    PNC2_Type = models.IntegerField(null=True)
    PNC2_Date = models.DateTimeField(null=True)
    PNC2_IFA_Tab = models.IntegerField(null=True)
    PNC2_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC2_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC2_PPC = models.CharField(null=True, max_length=255)
    PNC3_Type = models.IntegerField(null=True)
    PNC3_Date = models.DateTimeField(null=True)
    PNC3_IFA_Tab = models.IntegerField(null=True)
    PNC3_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC3_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC3_PPC = models.CharField(null=True, max_length=255)
    PNC4_Type = models.IntegerField(null=True)
    PNC4_Date = models.DateTimeField(null=True)
    PNC4_IFA_Tab = models.IntegerField(null=True)
    PNC4_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC4_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC4_PPC = models.CharField(null=True, max_length=255)
    PNC5_Type = models.IntegerField(null=True)
    PNC5_Date = models.DateTimeField(null=True)
    PNC5_IFA_Tab = models.IntegerField(null=True)
    PNC5_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC5_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC5_PPC = models.CharField(null=True, max_length=255)
    PNC6_Type = models.IntegerField(null=True)
    PNC6_Date = models.DateTimeField(null=True)
    PNC6_IFA_Tab = models.IntegerField(null=True)
    PNC6_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC6_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC6_PPC = models.CharField(null=True, max_length=255)
    PNC7_Type = models.IntegerField(null=True)
    PNC7_Date = models.DateTimeField(null=True)
    PNC7_IFA_Tab = models.IntegerField(null=True)
    PNC7_DangerSign_Mother = models.CharField(null=True, max_length=255)
    PNC7_ReferralFacility_Mother = models.CharField(null=True, max_length=255)
    PNC7_PPC = models.CharField(null=True, max_length=255)
    Mother_Death_Place = models.CharField(null=True, max_length=255)
    Mother_Death_Date = models.CharField(null=True, max_length=255)
    Mother_Death_Reason = models.CharField(null=True, max_length=255)
    Infant1_Term = models.CharField(null=True, max_length=255)
    Infant2_Id = models.CharField(null=True, max_length=255)
    Infant2_Name = models.CharField(null=True, max_length=255)
    Infant2_Term = models.CharField(null=True, max_length=255)
    Infant2_Resucitation_Done = models.CharField(null=True, max_length=255)
    Infant2_Weight = models.CharField(null=True, max_length=255)
    Infant2_Breast_Feeding = models.CharField(null=True, max_length=255)
    Infant3_Id = models.CharField(null=True, max_length=255)
    Infant3_Name = models.CharField(null=True, max_length=255)
    Infant3_Resucitation_Done = models.CharField(null=True, max_length=255)
    Infant4_Id = models.CharField(null=True, max_length=255)
    Infant4_Name = models.CharField(null=True, max_length=255)
    Infant4_Resucitation_Done = models.CharField(null=True, max_length=255)
    Infant5_Id = models.CharField(null=True, max_length=255)
    Infant5_Name = models.CharField(null=True, max_length=255)
    Infant5_Resucitation_Done = models.CharField(null=True, max_length=255)
    Infant6_Id = models.CharField(null=True, max_length=255)
    Infant6_Name = models.CharField(null=True, max_length=255)
    Infant6_Resucitation_Done = models.CharField(null=True, max_length=255)

    def sanitize_fields(self):
        try:
            if self.Delivery_Time:
                datetime.datetime.strptime(self.Delivery_Time, '%H:%M:%S')
        except ValueError:
            self.Delivery_Time = None

        try:
            if self.Discharge_Time:
                datetime.datetime.strptime(self.Discharge_Time, '%H:%M:%S')
        except ValueError:
            self.Discharge_Time = None

        if self.Maternal_Death:
            self.Maternal_Death = 0
            if self.Maternal_Death == 'Y' or self.Maternal_Death == 'y':
                self.Maternal_Death = 1

    @classmethod
    def accepted_fields(cls):
        return settings.RCH_PERMITTED_FIELDS['mother']

    @classmethod
    def update_beneficiaries(cls, beneficiary_type=MOTHER_DATA_TYPE, days_before=1):
        super(RCHMother, cls).update_beneficiaries(beneficiary_type, days_before)


class RCHChild(RCHRecord):
    RCH_Primary_Key = 'Child_RCH_ID_No'

    ANM_Name = models.CharField(null=True, max_length=255)
    ANM_Phone_No = models.BigIntegerField(null=True)
    ASHA_Name = models.CharField(null=True, max_length=255)
    ASHA_Phone_No = models.BigIntegerField(null=True)
    Birth_Date = models.DateTimeField(null=True)
    Child_Aadhaar_No = models.BigIntegerField(null=True)
    Child_RCH_ID_No = models.BigIntegerField(null=True)
    DPTBooster1_Antibiotics_Given = models.CharField(null=True, max_length=255)
    DPTBooster1_Breastfeeding = models.CharField(null=True, max_length=255)
    DPTBooster1_Complentary_Feeding = models.CharField(null=True, max_length=255)
    DPTBooster1_Diarrhoea = models.CharField(null=True, max_length=255)
    DPTBooster1_ORS_Given = models.CharField(null=True, max_length=255)
    DPTBooster1_Pneumonia = models.CharField(null=True, max_length=255)
    Delete_mother = models.CharField(null=True, max_length=255)
    Fully_Immunized = models.CharField(null=True, max_length=255)
    Gender = models.CharField(null=True, max_length=255)
    Measles1_Antibiotics_Given = models.CharField(null=True, max_length=255)
    Measles1_Breastfeeding = models.CharField(null=True, max_length=255)
    Measles1_Complentary_Feeding = models.CharField(null=True, max_length=255)
    Measles1_Diarrhoea = models.CharField(null=True, max_length=255)
    Measles1_ORS_Given = models.CharField(null=True, max_length=255)
    Measles1_Pneumonia = models.CharField(null=True, max_length=255)
    Mobile_Relates_To = models.CharField(null=True, max_length=255)
    Mother_Case_no = models.SmallIntegerField(null=True)
    Mother_RCH_ID_NO = models.BigIntegerField(null=True)
    Name_Child = models.CharField(null=True, max_length=255)
    Name_Father = models.CharField(null=True, max_length=255)
    Name_Mother = models.CharField(null=True, max_length=255)
    Received_AllVaccines = models.CharField(null=True, max_length=255)
    SubCentre_ID = models.SmallIntegerField(null=True)
    Village_Name = models.CharField(null=True, max_length=255)
    Weight = models.FloatField(null=True)
    Village_ID = models.IntegerField(null=True)

    Birth_place = models.CharField(null=True, max_length=255)
    Mother_MCTS_ID_No = models.CharField(null=True, max_length=255)
    Child_MCTS_ID_No = models.CharField(null=True, max_length=255)
    Child_EID = models.CharField(null=True, max_length=255)
    Birth_Certificate_Number = models.CharField(null=True, max_length=255)
    Entry_Type = models.CharField(null=True, max_length=255)
    Reason_closure = models.CharField(null=True, max_length=255)
    Death_reason = models.CharField(null=True, max_length=255)
    DeathPlace = models.CharField(null=True, max_length=255)
    DeathDate = models.DateTimeField(null=True)
    Case_closure = models.CharField(null=True, max_length=255)
    BCG_Dt = models.DateTimeField(null=True)
    OPV0_Dt = models.DateTimeField(null=True)
    OPV1_Dt = models.DateTimeField(null=True)
    OPV2_Dt = models.DateTimeField(null=True)
    OPV3_Dt = models.DateTimeField(null=True)
    OPVBooster_Dt = models.DateTimeField(null=True)
    DPT1_Dt = models.DateTimeField(null=True)
    DPT2_Dt = models.DateTimeField(null=True)
    DPT3_Dt = models.DateTimeField(null=True)
    DPTBooster1_Dt = models.DateTimeField(null=True)
    DPTBooster1_Complentary_Feeding_Month = models.CharField(null=True, max_length=255)
    DPTBooster1_Visit_Date = models.DateTimeField(null=True)
    DPTBooster2_Dt = models.DateTimeField(null=True)
    HepatitisB0_Dt = models.DateTimeField(null=True)
    HepatitisB1_Dt = models.DateTimeField(null=True)
    HepatitisB2_Dt = models.DateTimeField(null=True)
    HepatitisB3_Dt = models.DateTimeField(null=True)
    Penta1_Dt = models.DateTimeField(null=True)
    Penta2_Dt = models.DateTimeField(null=True)
    Penta3_Dt = models.DateTimeField(null=True)
    Measles1_Dt = models.DateTimeField(null=True)
    Measles1_Complentary_Feeding_Month = models.CharField(null=True, max_length=255)
    Measles1_Visit_Date = models.DateTimeField(null=True)
    Measles2_Dt = models.DateTimeField(null=True)
    JE1_Dt = models.DateTimeField(null=True)
    JE2_Dt = models.DateTimeField(null=True)
    VitA_Dose1_Dt = models.DateTimeField(null=True)
    VitA_Dose2_Dt = models.DateTimeField(null=True)
    VitA_Dose3_Dt = models.DateTimeField(null=True)
    VitA_Dose4_Dt = models.DateTimeField(null=True)
    VitA_Dose5_Dt = models.DateTimeField(null=True)
    VitA_Dose6_Dt = models.DateTimeField(null=True)
    VitA_Dose7_Dt = models.DateTimeField(null=True)
    VitA_Dose8_Dt = models.DateTimeField(null=True)
    VitA_Dose9_Dt = models.DateTimeField(null=True)
    MMR_Dt = models.DateTimeField(null=True)
    MR_Dt = models.DateTimeField(null=True)
    Typhoid_Dt = models.DateTimeField(null=True)
    Rota_Virus_Dt = models.DateTimeField(null=True)
    PNC1_No = models.CharField(null=True, max_length=255)
    PNC1_Type_Infant = models.IntegerField(null=True)
    PNC1_Date_Infant = models.DateTimeField(null=True)
    PNC1_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC1_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC1_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC2_No_Infant = models.IntegerField(null=True)
    PNC2_Type_Infant = models.IntegerField(null=True)
    PNC2_Date_Infant = models.DateTimeField(null=True)
    PNC2_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC2_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC2_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC3_No_Infant = models.IntegerField(null=True)
    PNC3_Type_Infant = models.IntegerField(null=True)
    PNC3_Date_Infant = models.DateTimeField(null=True)
    PNC3_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC3_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC3_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC4_No_Infant = models.IntegerField(null=True)
    PNC4_Type_Infant = models.IntegerField(null=True)
    PNC4_Date_Infant = models.DateTimeField(null=True)
    PNC4_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC4_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC4_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC5_No_Infant = models.IntegerField(null=True)
    PNC5_Type_Infant = models.IntegerField(null=True)
    PNC5_Date_Infant = models.DateTimeField(null=True)
    PNC5_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC5_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC5_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC6_No_Infant = models.IntegerField(null=True)
    PNC6_Type_Infant = models.IntegerField(null=True)
    PNC6_Date_Infant = models.DateTimeField(null=True)
    PNC6_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC6_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC6_Infant_Weight = models.CharField(null=True, max_length=255)
    PNC7_No_Infant = models.IntegerField(null=True)
    PNC7_Type_Infant = models.IntegerField(null=True)
    PNC7_Date_Infant = models.DateTimeField(null=True)
    PNC7_DangerSign_Infant = models.CharField(null=True, max_length=255)
    PNC7_ReferralFacility_Infant = models.CharField(null=True, max_length=255)
    PNC7_Infant_Weight = models.CharField(null=True, max_length=255)

    @classmethod
    def accepted_fields(cls):
        return settings.RCH_PERMITTED_FIELDS['child']

    @classmethod
    def update_beneficiaries(cls, beneficiary_type=CHILD_DATA_TYPE, days_before=1):
        super(RCHChild, cls).update_beneficiaries(beneficiary_type, days_before)


class AreaMapping(models.Model):
    stcode = models.IntegerField(null=False)
    stname = models.CharField(max_length=255, null=False)
    dtcode = models.IntegerField(null=False)
    dtname = models.CharField(max_length=255, null=False)
    pjcode = models.IntegerField(null=False)
    pjname = models.CharField(max_length=255, null=False)
    awcid = models.BigIntegerField(null=False)
    awcname = models.CharField(max_length=255, null=False)
    villcode = models.IntegerField(null=False)
    Village_name = models.CharField(max_length=255, null=False)

    @classmethod
    def fetch_village_ids_for_awcid(cls, awcid):
        return list(cls.objects.filter(awcid=awcid).values_list('villcode', flat=True).distinct().all())
