# -*- coding: utf-8 -*-

from datetime import datetime
import uuid
from nose.tools import nottest

from corehq.apps.domain.models import Domain
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.const import CASE_INDEX_EXTENSION, CASE_INDEX_CHILD
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from custom.enikshay.case_utils import CASE_TYPE_REFERRAL, CASE_TYPE_TRAIL
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    BACKUP_PHONE_NUMBER,
    MERM_ID,
    PERSON_FIRST_NAME,
    PERSON_LAST_NAME,
    TREATMENT_START_DATE,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    WEIGHT_BAND,
    ENROLLED_IN_PRIVATE,
    OTHER_NUMBER,
    TREATMENT_INITIATED_IN_PHI,
)
from corehq.apps.users.models import CommCareUser


def get_person_case_structure(case_id, user_id, extra_update=None, owner_id=None):
    extra_update = extra_update or {}
    owner_id = owner_id or uuid.uuid4().hex
    update = {
        'name': u"Peregrine เՇร ค Շгคק",
        PERSON_FIRST_NAME: u"Peregrine",
        PERSON_LAST_NAME: u"เՇร ค Շгคק",
        'aadhaar_number': "499118665246",
        'dob': "1987-08-15",
        'age': '20',
        'sex': 'male',
        'current_address': 'Mt. Everest',
        'secondary_contact_name_address': 'Mrs. Everestie',
        'previous_tb_treatment': 'yes',
        'nikshay_registered': "false",
        'husband_father_name': u"Mr. Peregrine เՇร ค Շгคק Kumar",
        'current_address_postal_code': '110088',
        'person_id': 'THX-1138',
    }
    update.update(extra_update)

    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "person",
            "user_id": user_id,
            "create": True,
            "owner_id": owner_id,
            "update": update
        },
    )


def get_occurrence_case_structure(case_id, indexed_person_case):
    return CaseStructure(
        case_id=case_id,
        attrs={
            'create': True,
            'case_type': 'occurrence',
            "update": dict(
                name="Occurrence #1",
            )
        },
        indices=[CaseIndex(
            indexed_person_case,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=indexed_person_case.attrs['case_type'],
        )],
    )


def get_episode_case_structure(case_id, indexed_occurrence_case, extra_update=None):
    extra_update = extra_update or {}
    update = {
        'date_of_diagnosis': '2014-09-09',
        'default_adherence_confidence': 'high',
        'disease_classification': 'extra_pulmonary',
        'episode_type': 'confirmed_tb',
        'hiv_status': 'reactive',
        'name': 'Episode #1',
        'occupation': 'engineer',
        'opened_on': datetime(1989, 6, 11, 0, 0),
        'patient_type_choice': 'treatment_after_lfu',
        'person_name': u'Peregrine เՇร ค Շгคק',
        'site_choice': 'pleural_effusion',
        'treatment_supporter_designation': 'ngo_volunteer',
        'treatment_initiated': TREATMENT_INITIATED_IN_PHI,
        TREATMENT_START_DATE: "2015-03-03",
        TREATMENT_SUPPORTER_FIRST_NAME: u"𝔊𝔞𝔫𝔡𝔞𝔩𝔣",
        TREATMENT_SUPPORTER_LAST_NAME: u"𝔗𝔥𝔢 𝔊𝔯𝔢𝔶",
        MERM_ID: "123456789",
        'treatment_initiation_status': 'F',
        'dst_status': 'pending',
        'basis_of_diagnosis': 'clinical_other',
    }
    update.update(extra_update)

    return CaseStructure(
        case_id=case_id,
        attrs={
            'create': True,
            'case_type': 'episode',
            "update": update
        },
        indices=[CaseIndex(
            indexed_occurrence_case,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=indexed_occurrence_case.attrs['case_type'],
        )],
    )


def get_adherence_case_structure(case_id, indexed_episode_id, adherence_date, extra_update=None):
    extra_update = extra_update or {}
    update = {
        "person_name": "Pippin",
        "adherence_confidence": "medium",
        "shared_number_99_dots": False,
        "adherence_date": adherence_date
    }
    update.update(extra_update)
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "adherence",
            "create": True,
            "update": update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_episode_id, attrs={"create": False}),
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type='episode',
        )],
        walk_related=False,
    )


def get_referral_case_structure(case_id, indexed_occurrence_id, extra_update=None):
    extra_update = extra_update or {}
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": CASE_TYPE_REFERRAL,
            "create": True,
            "update": extra_update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_occurrence_id, attrs={"create": False}),
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type='occurrence',
        )],
        walk_related=False,
    )


def get_prescription_case_structure(case_id, indexed_episode_id, extra_update=None):
    extra_update = extra_update or {}
    update = {
        'state': 'fulfilled',
    }
    update.update(extra_update)
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "prescription",
            "create": True,
            "update": update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_episode_id, attrs={"create": False}),
            identifier='episode_of_prescription',
            relationship=CASE_INDEX_EXTENSION,
            related_type='episode',
        )],
        walk_related=False,
    )


def get_prescription_item_case_structure(case_id, indexed_prescription_id, extra_update=None):
    extra_update = extra_update or {}
    update = {
        'state': 'fulfilled',
    }
    update.update(extra_update)
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "prescription_item",
            "create": True,
            "update": update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_prescription_id, attrs={"create": False}),
            identifier='prescription',
            relationship=CASE_INDEX_EXTENSION,
            related_type='prescription',
        )],
        walk_related=False,
    )


def get_voucher_case_structure(case_id, indexed_prescription_id, extra_update=None):
    # https://india.commcarehq.org/a/enikshay/apps/view/9340429733463e58ae0e1518defee221/summary/#/cases
    # https://docs.google.com/spreadsheets/d/1MCG205FOcsYsmKXHoSTjZ6A1iuqCIAESyleBl7G7PR8/
    extra_update = extra_update or {}
    update = {
        'state': 'fulfilled',
        'final_prescription_num_days': 10,
        'voucher_type': 'prescription',
    }
    update.update(extra_update)
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "voucher",
            "create": True,
            "update": update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_prescription_id, attrs={"create": False}),
            identifier='prescription_of_voucher',
            relationship=CASE_INDEX_EXTENSION,
            related_type='prescription',
        )],
        walk_related=False,  # TODO I'm not sure what this should be
    )


@nottest
def get_test_case_structure(case_id, indexed_occurrence_id, extra_update=None):
    extra_update = extra_update or {}
    update = dict(
        date_reported=datetime(2016, 8, 6).date(),
    )
    update.update(extra_update)
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "test",
            "create": True,
            "update": update
        },
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_occurrence_id, attrs={"create": False}),
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type='occurrence',
        )],
        walk_related=False,
    )


def get_trail_case_structure(case_id, indexed_occurrence_id, extra_update=None):
    extra_update = extra_update or {}
    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": CASE_TYPE_TRAIL,
            "create": True,
            "update": extra_update,
        },
        # Prior to 2017-08-01, the parent is a person or referral case
        indices=[CaseIndex(
            CaseStructure(case_id=indexed_occurrence_id, attrs={"create": False}),
            identifier='parent',
            relationship=CASE_INDEX_CHILD,
            related_type='occurrence',
        )],
        walk_related=False,
    )


class ENikshayCaseStructureMixin(object):
    def setUp(self):
        super(ENikshayCaseStructureMixin, self).setUp()
        delete_all_users()
        self.domain = getattr(self, 'domain', 'fake-domain-from-mixin')
        self.factory = CaseFactory(domain=self.domain)
        self.username = "jon-snow@user"
        self.password = "123"
        self.user = CommCareUser.create(
            self.domain,
            username=self.username,
            password=self.password,
            first_name="Jon",
            last_name="Snow",
        )
        self.person_id = u"person"
        self.occurrence_id = u"occurrence"
        self.episode_id = u"episode"
        self.test_id = u"test"
        self.lab_referral_id = u"lab_referral"
        self.prescription_id = "prescription_id"
        self.prescription_item_id = 'prescription_item_id'
        self.referral_id = 'referal'
        self.trail_id = 'trail'
        self._prescription_created = False
        self.primary_phone_number = "0123456789"
        self.secondary_phone_number = "0999999999"
        self.treatment_supporter_phone = "066000666"
        self.other_number = "0123456666"
        self._episode = None
        self._person = None

    def tearDown(self):
        delete_all_users()
        super(ENikshayCaseStructureMixin, self).tearDown()

    @property
    def person(self):
        if not self._person:
            self._person = get_person_case_structure(
                self.person_id,
                self.user.user_id,
                extra_update={
                    PRIMARY_PHONE_NUMBER: self.primary_phone_number,
                    BACKUP_PHONE_NUMBER: self.secondary_phone_number,
                    ENROLLED_IN_PRIVATE: 'false',
                }
            )
        return self._person

    @property
    def occurrence(self):
        return get_occurrence_case_structure(
            self.occurrence_id,
            self.person
        )

    @property
    def episode(self):
        if not self._episode:
            self._episode = get_episode_case_structure(
                self.episode_id,
                self.occurrence,
                extra_update={
                    OTHER_NUMBER: self.other_number,
                    TREATMENT_SUPPORTER_PHONE: self.treatment_supporter_phone,
                    WEIGHT_BAND: "adult_55-69"
                }
            )
        return self._episode

    def create_case(self, case):
        return self.factory.create_or_update_cases([case])

    def create_case_structure(self):
        return {case.case_id: case for case in self.factory.create_or_update_cases([self.episode])}

    @property
    def test(self):
        return CaseStructure(
            case_id=self.test_id,
            attrs={
                'create': True,
                'case_type': 'test',
                "update": dict(
                    date_reported=datetime(2016, 8, 6).date(),
                    lab_serial_number=19,
                    test_type_value="microscopy-zn",
                    purpose_of_testing="diagnostic",
                    result_grade="1plus",
                    testing_facility_id=self.dmc.get_id,
                )
            },
            indices=[CaseIndex(
                self.occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.occurrence.attrs['case_type'],
            )],
        )

    @property
    def lab_referral(self):
        return CaseStructure(
            case_id=self.lab_referral_id,
            attrs={
                'create': True,
                'case_type': 'lab_referral',
                'owner_id': self.dmc.get_id,
                "update": {}
            },
            indices=[CaseIndex(
                self.test,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.test.attrs['case_type'],
            )],
        )

    def create_adherence_cases(self, adherence_dates, adherence_source='99DOTS'):
        return self.factory.create_or_update_cases([
            get_adherence_case_structure(
                adherence_date.strftime('%Y-%m-%d-%H-%M'),
                self.episode_id,
                adherence_date,
                extra_update={
                    "name": adherence_date,
                    "adherence_source": adherence_source,
                    "adherence_value": "unobserved_dose",
                }
            )
            for adherence_date in adherence_dates
        ])

    def create_adherence_case(self, adherence_date, adherence_source="99DOTS", adherence_value="unobserved_dose",
                              case_id=None):
        return self.factory.create_or_update_cases([
            get_adherence_case_structure(case_id, self.episode_id, adherence_date, extra_update={
                "adherence_source": adherence_source,
                "adherence_value": adherence_value,
            })
        ])

    def create_prescription_case(self, prescription_id=None, extra_update=None):
        return self.factory.create_or_update_case(
            get_prescription_case_structure(prescription_id or uuid.uuid4().hex, self.episode_id, extra_update)
        )[0]

    def create_prescription_item_case(self, prescription_case_id, prescription_item_case_id=None):
        return self.factory.create_or_update_case(
            get_prescription_item_case_structure(
                prescription_item_case_id or uuid.uuid4().hex,
                prescription_case_id
            )
        )[0]

    def create_voucher_case(self, prescription_id, extra_update=None):
        return self.factory.create_or_update_case(
            get_voucher_case_structure(uuid.uuid4().hex, prescription_id, extra_update)
        )[0]

    def create_referral_case(self, case_id):
        return self.factory.create_or_update_cases([
            get_referral_case_structure(case_id, self.occurrence_id)
        ])

    @nottest
    def create_test_case(self, occurrence_id, extra_update=None):
        return self.factory.create_or_update_case(
            get_test_case_structure(uuid.uuid4().hex, occurrence_id, extra_update)
        )[0]

    def create_lab_referral_case(self):
        return self.factory.create_or_update_case(
            self.lab_referral,
        )[0]

    def create_trail_case(self):
        return self.factory.create_or_update_case(
            get_trail_case_structure(self.trail_id, self.occurrence_id)
        )[0]


class ENikshayLocationStructureMixin(object):
    def setUp(self):
        self.domain = getattr(self, 'domain', 'fake-domain-from-mixin')
        self.project = Domain(name=self.domain)
        self.project.save()
        _, locations = setup_enikshay_locations(self.domain)
        self.locations = locations

        self.ctd = locations['CTD']

        self.sto = locations['STO']
        self.sto.metadata = {
            'nikshay_code': 'MH',
            'is_test': 'no',
        }
        self.sto.save()

        self.cto = locations['CTO']

        self.dto = locations['DTO']
        self.dto.metadata = {
            'nikshay_code': 'ABD',
            'is_test': 'no',
        }
        self.dto.save()

        self.drtb_hiv = locations['DRTB-HIV']
        self.drtb_hiv.save()

        self.tu = locations['TU']
        self.tu.metadata = {
            'nikshay_code': '1',
            'is_test': 'no',
        }
        self.tu.save()

        self.phi = locations['PHI']
        self.phi.metadata = {
            'nikshay_code': '2',
            'is_test': 'no',
        }
        self.phi.save()

        self.dmc = locations['DMC']
        self.dmc.metadata = {
            'nikshay_code': '123',
            'is_test': 'no',
        }
        self.dmc.save()

        self.pcp = locations['PCP']
        self.pcp.metadata = {
            'nikshay_code': '1234567',
            'is_test': 'no',
            'nikshay_tu_id': '1',
        }
        self.pcp.save()

        self.pcc = locations['PCC']
        self.pcc.metadata = {
            'nikshay_code': '1234567',
            'is_test': 'no',
        }
        self.pcc.save()

        self.plc = locations['PLC']
        self.plc.metadata = {
            'nikshay_code': '1234567',
            'is_test': 'no',
        }
        self.plc.save()
        self.pac = locations['PLC']
        self.pac.metadata = {
            'nikshay_code': '1234567',
            'is_test': 'no',
        }
        self.pac.save()
        super(ENikshayLocationStructureMixin, self).setUp()

    def tearDown(self):
        self.project.delete()
        super(ENikshayLocationStructureMixin, self).tearDown()

    def assign_person_to_location(self, location_id):
        return self.create_case(
            CaseStructure(
                case_id=self.person_id,
                attrs={
                    "update": dict(
                        owner_id=location_id,
                    )
                }
            )
        )[0]


def setup_enikshay_locations(domain_name):
    location_type_structure = [
        LocationTypeStructure('ctd', [
            LocationTypeStructure('sto', [
                LocationTypeStructure('cto', [
                    LocationTypeStructure('dto', [
                        LocationTypeStructure('tu', [
                            LocationTypeStructure('phi', []),
                            LocationTypeStructure('dmc', []),
                        ]),
                        LocationTypeStructure('drtb-hiv', []),
                        LocationTypeStructure('pac', []),
                        LocationTypeStructure('pcc', []),
                        LocationTypeStructure('pcp', []),
                        LocationTypeStructure('pdr', []),
                        LocationTypeStructure('plc', []),
                    ])
                ]),
                LocationTypeStructure('drtb', []),
                LocationTypeStructure('cdst', []),
            ])
        ])
    ]
    location_structure = [
        LocationStructure('CTD', 'ctd', [
            LocationStructure('STO', 'sto', [
                LocationStructure('CTO', 'cto', [
                    LocationStructure('DTO', 'dto', [
                        LocationStructure('TU', 'tu', [
                            LocationStructure('PHI', 'phi', []),
                            LocationStructure('DMC', 'dmc', []),
                        ]),
                        LocationStructure('DRTB-HIV', 'drtb-hiv', []),
                        LocationStructure('PAC', 'pac', []),
                        LocationStructure('PCC', 'pcc', []),
                        LocationStructure('PCP', 'pcp', []),
                        LocationStructure('PDR', 'pdr', []),
                        LocationStructure('PLC', 'plc', []),
                    ])
                ]),
                LocationStructure('DRTB', 'drtb', []),
                LocationStructure('CDST', 'cdst', []),
            ])
        ])
    ]

    location_metadata = {'is_test': 'no', 'nikshay_code': 'nikshay_code'}
    return (setup_location_types_with_structure(domain_name, location_type_structure),
            setup_locations_with_structure(domain_name, location_structure, location_metadata))
