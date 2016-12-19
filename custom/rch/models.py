import datetime
from django.db import models
from custom.rch.utils import fetch_mother_beneficiaries_records, fetch_child_beneficiaries_records


STATE_DISTRICT_MAPPING = {
    '28': [
        '523'
    ]
}


class RCHRecord(models.Model):
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
    PHC_Name = models.CharField(null=True, max_length=255)
    PHC_ID = models.IntegerField(null=True)
    Subcentre_Name = models.CharField(null=True, max_length=255)
    Village_ID = models.IntegerField(null=True)
    Mobile_no = models.BigIntegerField(null=True)
    Religion = models.CharField(null=True, max_length=255)
    State_Name = models.CharField(null=True, max_length=255)
    StateID = models.PositiveSmallIntegerField(null=True)
    Updated_On = models.DateTimeField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class RCHMother(RCHRecord):
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

    def save(self, *args, **kwargs):
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

        super(RCHMother, self).save(*args, **kwargs)

    @classmethod
    def update_beneficiaries(cls):
        date_str = str(datetime.date.fromordinal(datetime.date.today().toordinal()-1))
        for state_id in STATE_DISTRICT_MAPPING:
            for district_id in STATE_DISTRICT_MAPPING[state_id]:
                records = fetch_mother_beneficiaries_records(date_str, date_str, state_id, district_id)
                for record in records:
                    rch_mother = cls()
                    for prop in record:
                        rch_mother.__setattr__(prop.keys()[0], prop.values()[0])
                    rch_mother.save()


class RCHChild(RCHRecord):
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
    MDDS_VillageID = models.IntegerField(null=True)
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
    VILLAGE_Name = models.CharField(null=True, max_length=255)
    Weight = models.FloatField(null=True)

    @classmethod
    def update_beneficiaries(cls):
        date_str = str(datetime.date.fromordinal(datetime.date.today().toordinal()-1))
        for state_id in STATE_DISTRICT_MAPPING:
            for district_id in STATE_DISTRICT_MAPPING[state_id]:
                records = fetch_child_beneficiaries_records(date_str, date_str, state_id, district_id)
                for record in records:
                    rch_child = cls()
                    for prop in record:
                        rch_child.__setattr__(prop.keys()[0], prop.values()[0])
                    rch_child.save()


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
