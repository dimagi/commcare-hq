import datetime
from django.db import models
from django.conf import settings
from custom.rch.utils import fetch_beneficiaries_records, MOTHER_RECORD_TYPE, CHILD_RECORD_TYPE
from jsonfield.fields import JSONField


STATE_DISTRICT_MAPPING = {
    '28': [  # Andhra Pradesh
        '523'  # West Godavari
    ]
}

# For every record type in RCH there is a corresponding value here which is then used
# like for display options or maintaining permitted fields
RCH_RECORD_TYPE_MAPPING = {
    MOTHER_RECORD_TYPE: 'mother',
    CHILD_RECORD_TYPE: 'child',
}


class RCHRecord(models.Model):
    cas_case_id = models.CharField(null=True, max_length=255)
    details = JSONField(default=dict)
    district_id = models.PositiveSmallIntegerField(null=True)
    state_id = models.PositiveSmallIntegerField(null=True)
    village_id = models.IntegerField(null=True)
    village_name = models.CharField(null=True, max_length=255)
    name = models.CharField(null=True, max_length=255)
    aadhar_num = models.BigIntegerField(null=True)
    dob = models.DateTimeField(null=True)
    rch_id = models.BigIntegerField(null=True)
    doc_type = models.CharField(max_length=1, null=False,
                                choices=[(k, v) for k, v in RCH_RECORD_TYPE_MAPPING.items()])

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    @classmethod
    def accepted_fields(cls, beneficiary_type):
        """
        :param beneficiary_type: can be any of the keys in RCH_RECORD_TYPE_MAPPING
        :return: fields that are expected to be received from RCH
        """
        if beneficiary_type in RCH_RECORD_TYPE_MAPPING:
            return settings.RCH_PERMITTED_FIELDS[RCH_RECORD_TYPE_MAPPING[beneficiary_type]]
        else:
            return set()

    def mother_record(self):
        return self.doc_type == MOTHER_RECORD_TYPE

    def child_record(self):
        return self.doc_type == CHILD_RECORD_TYPE

    @classmethod
    def _get_rch_id_key(cls, beneficiary_type):
        # This gives the corresponding field that contains the RCH_ID when records are received from RCH
        # which then gets saved as the rch_id field and later used for filtering by RCH_ID when needed
        if beneficiary_type == MOTHER_RECORD_TYPE:
            return 'Registration_no'
        elif beneficiary_type == CHILD_RECORD_TYPE:
            return 'Child_RCH_ID_No'

    @property
    def rch_id_key(self):
        return self._get_rch_id_key(self.doc_type)

    def _set_mother_fields(self, dict_of_props):
        self.aadhar_num = dict_of_props['PW_Aadhar_No']
        self.name = dict_of_props['Name_wife']
        self.dob = dict_of_props['Mother_BirthDate']

    def _set_child_fields(self, dict_of_props):
        self.aadhar_num = dict_of_props['Child_Aadhaar_No']
        self.name = dict_of_props['Name_Child']
        self.dob = dict_of_props['Birth_Date']

    def _set_custom_fields(self, dict_of_props):
        if self.mother_record():
            self._set_mother_fields(dict_of_props)
        elif self.child_record():
            self._set_child_fields(dict_of_props)

    def set_beneficiary_fields(self, dict_of_props):
        self.district_id = dict_of_props['MDDS_DistrictID']
        self.state_id = dict_of_props['MDDS_StateID']
        self.village_id = dict_of_props['MDDS_VillageID']
        self.rch_id = dict_of_props[self.rch_id_key]
        self.village_name = dict_of_props.get('Village_Name')
        self._set_custom_fields(dict_of_props)

    @classmethod
    def update_beneficiaries(cls, beneficiary_type, days_before=1):
        date_str = str(datetime.date.fromordinal(datetime.date.today().toordinal() - days_before))
        for state_id in STATE_DISTRICT_MAPPING:
            for district_id in STATE_DISTRICT_MAPPING[state_id]:
                records = fetch_beneficiaries_records(date_str, date_str, state_id, beneficiary_type, district_id)
                for record in records:
                    # convert list of dicts of properties to a single dict
                    dict_of_props = {}
                    for prop in record:
                        if prop.keys()[0] in cls.accepted_fields(beneficiary_type):
                            dict_of_props[prop.keys()[0]] = prop.values()[0]

                    rch_id_key_field = cls._get_rch_id_key(beneficiary_type)
                    record_pk = dict_of_props[rch_id_key_field]
                    assert record_pk
                    results = cls.objects.filter(rch_id=record_pk)

                    if results:
                        rch_beneficiary = results[0]
                        rch_beneficiary.details = dict_of_props
                    else:
                        rch_beneficiary = cls(doc_type=beneficiary_type)

                    rch_beneficiary.set_beneficiary_fields(dict_of_props)
                    rch_beneficiary.details = dict_of_props
                    rch_beneficiary.save()


class AreaMapping(models.Model):
    stcode = models.IntegerField(null=False)
    stname = models.CharField(max_length=255, null=False)
    dtcode = models.IntegerField(null=False)
    dtname = models.CharField(max_length=255, null=False)
    pjcode = models.IntegerField(null=False)
    pjname = models.CharField(max_length=255, null=False)
    awcid = models.BigIntegerField(null=False)
    awcname = models.CharField(max_length=255, null=False)
    village_code = models.IntegerField(null=False)
    village_name = models.CharField(max_length=255, null=False)

    @classmethod
    def fetch_awc_ids_for_state(cls, state_id):
        return list(cls.objects.filter(stcode=state_id).values_list('awcid', flat=True).distinct().all())

    @classmethod
    def fetch_village_ids_for_state(cls, state_id):
        return list(cls.objects.filter(stcode=state_id).values_list('village_code', flat=True).distinct().all())

    @classmethod
    def fetch_awc_ids_for_district(cls, district_id):
        return list(cls.objects.filter(dtcode=district_id).values_list('awcid', flat=True).distinct().all())

    @classmethod
    def fetch_village_ids_for_district(cls, district_id):
        return list(cls.objects.filter(dtcode=district_id).values_list('village_code', flat=True).distinct().all())

    @classmethod
    def fetch_awc_ids_for_village_id(cls, village_id):
        return list(cls.objects.filter(village_code=village_id).values_list('awcid', flat=True).distinct().all())

    @classmethod
    def fetch_village_ids_for_awcid(cls, awcid):
        return list(cls.objects.filter(awcid=awcid).values_list('village_code', flat=True).distinct().all())
