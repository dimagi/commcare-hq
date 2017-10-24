import datetime
from django.db import models
from custom.rch.utils import (
    fetch_beneficiaries_records,
    find_matching_cas_record_id,
)
from jsonfield.fields import JSONField
from custom.rch.const import (
    STATE_DISTRICT_MAPPING,
    RCH_RECORD_TYPE_MAPPING,
    RCH_PERMITTED_FIELDS,
)


class RCHRecord(models.Model):
    _rch_id_key = None
    _beneficiary_type = None

    cas_case_id = models.CharField(null=True, max_length=255)  # ICDS-CAS case that was found as a match
    details = JSONField(default=dict)  # all details received from RCH for this beneficiary
    district_id = models.PositiveSmallIntegerField(null=True)
    state_id = models.PositiveSmallIntegerField(null=True)
    village_id = models.IntegerField(null=True)
    village_name = models.CharField(null=True, max_length=255)
    name = models.CharField(null=True, max_length=255)
    aadhar_num = models.BigIntegerField(null=True)
    dob = models.DateTimeField(null=True)
    rch_id = models.BigIntegerField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def beneficiary_type(self):
        return self._beneficiary_type

    @classmethod
    def accepted_fields(cls):
        """
        :param beneficiary_type: can be any of the keys in RCH_RECORD_TYPE_MAPPING like 1 for mother
        :return: fields that are expected to be received from RCH
        """
        beneficiary_type = cls._beneficiary_type  # mother, child etc
        if beneficiary_type in RCH_RECORD_TYPE_MAPPING.values():
            return RCH_PERMITTED_FIELDS[beneficiary_type]
        else:
            return set()

    @property
    def rch_id_key(self):
        return self._rch_id_key

    def _set_custom_fields(self, dict_of_props):
        raise NotImplementedError

    def assign_search_fields(self, dict_of_props):
        # set fields from details received from RCH that are specifically used for quick lookup for
        # filtering or matching
        self.district_id = dict_of_props['MDDS_DistrictID']
        self.state_id = dict_of_props['MDDS_StateID']
        self.village_id = dict_of_props['MDDS_VillageID']
        self.rch_id = dict_of_props[self.rch_id_key]
        self.village_name = dict_of_props.get('Village_Name')
        self._set_custom_fields(dict_of_props)

    @classmethod
    def update_beneficiaries(cls, days_before=1):
        rch_beneficiary_type = RCH_RECORD_TYPE_MAPPING.get(cls._beneficiary_type)
        date_str = str(datetime.date.fromordinal(datetime.date.today().toordinal() - days_before))
        for state_id in STATE_DISTRICT_MAPPING:
            for district_id in STATE_DISTRICT_MAPPING[state_id]:
                records = fetch_beneficiaries_records(date_str, state_id, rch_beneficiary_type, district_id)
                for record in records:
                    # convert list of dicts of properties to a single dict
                    dict_of_props = {}
                    for prop in record:
                        if prop.keys()[0] in cls.accepted_fields():
                            dict_of_props[prop.keys()[0]] = prop.values()[0]

                    rch_id_key_field = cls._rch_id_key
                    record_pk = dict_of_props[rch_id_key_field]
                    assert record_pk
                    # Find corresponding record if already present using RCH ID
                    rch_beneficiary = cls.objects.filter(rch_id=record_pk).first()
                    # else initialize if new record to be added
                    if not rch_beneficiary:
                        rch_beneficiary = cls()

                    rch_beneficiary.assign_search_fields(dict_of_props)
                    rch_beneficiary.details = dict_of_props
                    rch_beneficiary.save()

    def associate_matching_cas_record(self):
        matching_icds_cas_case_id = find_matching_cas_record_id(self.aadhar_num)
        if matching_icds_cas_case_id:
            self.cas_case_id = matching_icds_cas_case_id
            self.save()


class RCHMotherRecord(RCHRecord):
    _rch_id_key = 'Registration_no'
    _beneficiary_type = 'mother'

    def _set_custom_fields(self, dict_of_props):
        self.aadhar_num = dict_of_props['PW_Aadhar_No']
        self.name = dict_of_props['Name_wife']
        self.dob = dict_of_props['Mother_BirthDate']


class RCHChildRecord(RCHRecord):
    _rch_id_key = 'Child_RCH_ID_No'
    _beneficiary_type = 'child'

    def _set_custom_fields(self, dict_of_props):
        self.aadhar_num = dict_of_props['Child_Aadhaar_No']
        self.name = dict_of_props['Name_Child']
        self.dob = dict_of_props['Birth_Date']


class AreaMapping(models.Model):
    stcode = models.IntegerField(db_index=True)
    stname = models.CharField(max_length=255)
    dtcode = models.IntegerField(db_index=True)
    dtname = models.CharField(max_length=255)
    pjcode = models.IntegerField()
    pjname = models.CharField(max_length=255)
    awcid = models.BigIntegerField(db_index=True)
    awcname = models.CharField(max_length=255)
    village_code = models.IntegerField(db_index=True)
    village_name = models.CharField(max_length=255)

    @classmethod
    def fetch_awc_ids_for_state(cls, state_id):
        return list(cls.objects.filter(stcode=state_id).values_list('awcid', flat=True).distinct())

    @classmethod
    def fetch_village_ids_for_state(cls, state_id):
        return list(cls.objects.filter(stcode=state_id).values_list('village_code', flat=True).distinct())

    @classmethod
    def fetch_awc_ids_for_district(cls, district_id):
        return list(cls.objects.filter(dtcode=district_id).values_list('awcid', flat=True).distinct())

    @classmethod
    def fetch_village_ids_for_district(cls, district_id):
        return list(cls.objects.filter(dtcode=district_id).values_list('village_code', flat=True).distinct())

    @classmethod
    def fetch_awc_ids_for_village_id(cls, village_id):
        return list(cls.objects.filter(village_code=village_id).values_list('awcid', flat=True).distinct())

    @classmethod
    def fetch_village_ids_for_awcid(cls, awcid):
        return list(cls.objects.filter(awcid=awcid).values_list('village_code', flat=True).distinct())
