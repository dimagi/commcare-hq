from datetime import date, datetime

from django.db import models


def _parse_datetime_or_null_to_date(datetime_str):
    if datetime_str == 'NULL':
        return ''
    else:
        return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f').date()


class PatientDetail(models.Model):
    PregId = models.CharField(max_length=255, primary_key=True)
    scode = models.CharField(max_length=255, null=True)
    Dtocode = models.CharField(max_length=255, null=True)
    Tbunitcode = models.IntegerField()
    pname = models.CharField(max_length=255)
    pgender = models.CharField(
        max_length=255,
        choices=(
            ('F', 'F'),
            ('M', 'M'),
            ('T', 'T'),
        ),
    )
    page = models.IntegerField()
    poccupation = models.CharField(max_length=255)
    paadharno = models.BigIntegerField(null=True)
    paddress = models.CharField(max_length=255)
    pmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    plandline = models.CharField(max_length=255, null=True)
    ptbyr = models.CharField(max_length=255, null=True)  # dates, but not clean
    cname = models.CharField(max_length=255, null=True)
    caddress = models.CharField(max_length=255, null=True)
    cmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    clandline = models.CharField(max_length=255, null=True)
    cvisitedby = models.CharField(max_length=255, null=True)
    dcpulmunory = models.CharField(
        max_length=255,
        choices=(
            ('y', 'y'),
            ('Y', 'Y'),
            ('N', 'N'),
            ('P', 'P'),
        ),
    )
    dcexpulmunory = models.CharField(max_length=255)
    dcpulmunorydet = models.CharField(max_length=255, null=True)
    dotname = models.CharField(max_length=255, null=True)
    dotdesignation = models.CharField(max_length=255, null=True)
    dotmob = models.CharField(max_length=255, null=True)  # validate numerical in factory
    dotlandline = models.CharField(max_length=255, null=True)
    dotpType = models.CharField(max_length=255)
    dotcenter = models.CharField(max_length=255, null=True)
    PHI = models.IntegerField()
    dotmoname = models.CharField(max_length=255, null=True)
    dotmosdone = models.CharField(max_length=255)
    atbtreatment = models.CharField(
        max_length=255,
        choices=(
            ('Y', 'Y'),
            ('N', 'N'),
        ),
        null=True,
    )
    atbduration = models.CharField(max_length=255, null=True)  # some int, some # months poorly formatted
    atbsource = models.CharField(
        max_length=255,
        choices=(
            ('G', 'G'),
            ('N', 'N'),
            ('O', 'O'),
            ('P', 'P'),
        ),
        null=True,
    )
    atbregimen = models.CharField(max_length=255, null=True)
    atbyr = models.CharField(max_length=255, null=True)
    Ptype = models.CharField(max_length=255)
    pcategory = models.CharField(max_length=255)
    regBy = models.CharField(max_length=255)
    regDate = models.CharField(max_length=255)
    isRntcp = models.CharField(max_length=255)
    dotprovider_id = models.CharField(max_length=255)
    pregdate1 = models.DateField()
    cvisitedDate1 = models.CharField(max_length=255)
    InitiationDate1 = models.CharField(max_length=255)  # datetime or 'NULL'
    dotmosignDate1 = models.CharField(max_length=255)  # datetime or 'NULL'

    @property
    def first_name(self):
        return ' '.join(self._list_of_names[:-1])

    @property
    def last_name(self):
        return self._list_of_names[-1]

    @property
    def _list_of_names(self):
        return self.pname.split(' ')

    @property
    def sex(self):
        return {
            'F': 'female',
            'M': 'male',
            'T': 'transgender'
        }[self.pgender]

    @property
    def disease_classification(self):
        pulmonary = 'pulmonary'
        extra_pulmonary = 'extra_pulmonary'
        return {
            'y': pulmonary,
            'Y': pulmonary,
            'P': pulmonary,
            'N': extra_pulmonary,
        }[self.dcpulmunory]

    @property
    def site_choice(self):
        return {
            '0': 'other',
            '1': 'lymph_node',
            '2': 'pleural_effusion',
            '3': 'abdominal',
            '4': 'other',
            '5': 'brain',
            '6': 'spine',
            '7': 'other',
            '8': 'other',
            '9': 'other',
            '10': 'other',
        }.get(self.dcexpulmunory.strip(), '')

    @property
    def patient_type_choice(self):
        return {
            '1': 'new',
            '2': 'recurrent',
            '3': 'treatment_after_failure',
            '4': 'treatment_after_lfu',
            '5': 'transfer_in',
            '6': 'transfer_in',
            '7': 'transfer_in',
        }[self.Ptype]

    @property
    def occupation(self):
        return {
            '0': 'undetermined_by_migration',
            '1': 'legislators_or_senior_official',
            '2': 'corporate_manager',
            '3': 'general_manager',
            '4': 'physical_mathematical_and_engineering',
            '5': 'life_sciences_and_health',
            '6': 'teaching_professional',
            '7': 'other_professional',
            '8': 'physical_and_engineering_science_associate',
            '9': 'life_sciences_and_health_associate',
            '10': 'teaching_associate',
            '11': 'other_associate',
            '12': 'office_clerk',
            '13': 'customer_services_clerk',
            '14': 'person_protective_service_provider',
            '15': 'model_sales_persons_demonstrator',
            '16': 'market_oriented_agriculture_fishery',
            '17': 'subsistence_agriculture_fishery',
            '18': 'extraction_and_building_trade',
            '19': 'metal_machinery_and_related',
            '20': 'precision_handicraft_printing_and_related',
            '21': 'other_craft_and_related',
            '22': 'stationary_plant_and_related',
            '23': 'machine_operator_or_assembler',
            '24': 'driver_and_mobile_plant_operator',
            '25': 'sales_and_services_elementary',
            '26': 'agriculture_fishery_and_related',
            '27': 'mining_construction_manufacturing_transport',
            '28': 'new_worker_seeking_employment',
            '29': 'occupation_unidentifiable',
            '30': 'no_occupation_reported',
        }[self.poccupation]

    @property
    def treatment_supporter_designation(self):
        return {
            '0': 'undetermined_by_migration',
            '1': 'health_worker',
            '2': 'tbhv',
            '3': 'asha_or_other_phi_hw',
            '4': 'aww',
            '5': 'ngo_volunteer',
            '6': 'private_medical_pracitioner',
            '7': 'other_community_volunteer',
        }[self.dotpType]

    @property
    def treatment_supporter_first_name(self):
        return ' '.join(self._list_of_dot_names[:-1]) if len(self._list_of_dot_names) > 1 else ''

    @property
    def treatment_supporter_last_name(self):
        return self._list_of_dot_names[-1]

    @property
    def _list_of_dot_names(self):
        return self.dotname.split(' ') if self.dotname else ['']

    @property
    def treatment_initiation_date(self):
        return _parse_datetime_or_null_to_date(self.InitiationDate1)

    @property
    def date_of_mo_signature(self):
        return _parse_datetime_or_null_to_date(self.dotmosignDate1)

    @property
    def ihv_date(self):
        ihv_date_or_blank = _parse_datetime_or_null_to_date(self.cvisitedDate1)
        if ihv_date_or_blank and ihv_date_or_blank == date(1900, 1, 1):
            return ''
        else:
            return ihv_date_or_blank

    @property
    def initial_home_visit_status(self):
        return 'completed' if self.ihv_date else 'pending'


class Outcome(models.Model):
    PatientId = models.OneToOneField(PatientDetail, primary_key=True)
    Outcome = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
            ('0', '0'),
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
            ('5', '5'),
            ('6', '6'),
            ('7', '7'),
        )
    )
    OutcomeDate = models.CharField(max_length=255, null=True)  # somethings DD/MM/YYYY, sometimes DD-MM-YYYY
    MO = models.CharField(max_length=255, null=True)  # doctor's name
    XrayEPTests = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
        ),
    )
    MORemark = models.CharField(max_length=255, null=True)  # doctor's notes
    HIVStatus = models.CharField(
        max_length=255,
        choices=(
            ('NULL', 'NULL'),
            ('Pos', 'Pos'),
            ('Neg', 'Neg'),
            ('Unknown', 'Unknown'),
        ),
        null=True,
    )
    HIVTestDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    CPTDeliverDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    ARTCentreDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    InitiatedOnART = models.IntegerField(
        choices=(
            (0, 0),
            (1, 1),
        ),
        null=True,
    )
    InitiatedDate = models.CharField(max_length=255, null=True)  # dates, None, and NULL
    userName = models.CharField(max_length=255)
    loginDate = models.DateTimeField()
    OutcomeDate1 = models.CharField(max_length=255)  # datetimes and NULL

    @property
    def hiv_status(self):
        return {
            None: None,
            'NULL': None,
            'Pos': 'reactive',
            'Neg': 'non_reactive',
            'Unknown': 'unknown',
        }[self.HIVStatus]


# class Household(models.Model):
#     PatientID = models.ForeignKey(APatientDetail)  # have to move to end of excel CSV
#     Name = models.CharField(max_length=255, null=True)
#     Dosage = models.CharField(max_length=255, null=True)
#     Weight = models.CharField(max_length=255, null=True)
#     M1 = models.CharField(max_length=255, null=True)
#     M2 = models.CharField(max_length=255, null=True)
#     M3 = models.CharField(max_length=255, null=True)
#     M4 = models.CharField(max_length=255, null=True)
#     M5 = models.CharField(max_length=255, null=True)
#     M6 = models.CharField(max_length=255, null=True)
