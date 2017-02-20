from datetime import datetime
import uuid

from corehq.apps.domain.models import Domain
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation, LocationType
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
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
)
from corehq.apps.users.models import CommCareUser


def get_person_case_structure(case_id, user_id, extra_update={}):
    update = {
        'name': "Peregrine Took",
        PERSON_FIRST_NAME: "Peregrine",
        PERSON_LAST_NAME: "Took",
        'aadhaar_number': "499118665246",
        MERM_ID: "123456789",
        'dob': "1987-08-15",
        'age': '20',
        'sex': 'male',
        'current_address': 'Mr. Everest',
        'secondary_contact_name_address': 'Mrs. Everestie',
        'previous_tb_treatment': 'yes',
        'nikshay_registered': "false",
    }
    update.update(extra_update)

    return CaseStructure(
        case_id=case_id,
        attrs={
            "case_type": "person",
            "user_id": user_id,
            "create": True,
            "owner_id": uuid.uuid4().hex,
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


def get_episode_case_structure(case_id, indexed_occurrence_case, extra_update={}):
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
        'person_name': 'Peregrine Took',
        'site_choice': 'pleural_effusion',
        'treatment_supporter_designation': 'ngo_volunteer',
        TREATMENT_START_DATE: "2015-03-03",
        TREATMENT_SUPPORTER_FIRST_NAME: "Gandalf",
        TREATMENT_SUPPORTER_LAST_NAME: "The Grey",
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


def get_adherence_case_structure(indexed_episode_id, adherence_date, extra_update={}):
    update = {
        "person_name": "Pippin",
        "adherence_confidence": "medium",
        "shared_number_99_dots": False,
        "adherence_date": adherence_date
    }
    update.update(extra_update)
    return CaseStructure(
        case_id=adherence_date.strftime('%Y-%m-%d-%H-%M'),
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


class ENikshayCaseStructureMixin(object):
    def setUp(self):
        super(ENikshayCaseStructureMixin, self).setUp()
        delete_all_users()
        self.domain = getattr(self, 'domain', 'fake-domain-from-mixin')
        self.factory = CaseFactory(domain=self.domain)
        self.user = CommCareUser.create(
            self.domain,
            "jon-snow@user",
            "123",
        )
        self.person_id = u"person"
        self.occurrence_id = u"occurrence"
        self.episode_id = u"episode"
        self.primary_phone_number = "0123456789"
        self.secondary_phone_number = "0999999999"
        self.treatment_supporter_phone = "066000666"

    def tearDown(self):
        delete_all_users()
        super(ENikshayCaseStructureMixin, self).tearDown()

    @property
    def person(self):
        return get_person_case_structure(
            self.person_id,
            self.user.user_id,
            extra_update={
                PRIMARY_PHONE_NUMBER: self.primary_phone_number,
                BACKUP_PHONE_NUMBER: self.secondary_phone_number,
            }
        )

    @property
    def occurrence(self):
        return get_occurrence_case_structure(
            self.occurrence_id,
            self.person
        )

    @property
    def episode(self):
        return get_episode_case_structure(
            self.episode_id,
            self.occurrence,
            extra_update={TREATMENT_SUPPORTER_PHONE: self.treatment_supporter_phone}
        )

    def create_case(self, case):
        return self.factory.create_or_update_cases([case])

    def create_case_structure(self):
        return {case.case_id: case for case in self.factory.create_or_update_cases([self.episode])}

    def create_adherence_cases(self, adherence_dates, adherence_source='99DOTS'):
        return self.factory.create_or_update_cases([
            get_adherence_case_structure(
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


class ENikshayLocationStructureMixin(object):
    def setUp(self):
        self.domain = getattr(self, 'domain', 'fake-domain-from-mixin')
        self.project = Domain(name=self.domain)
        self.project.save()
        locations = self._setup_enikshay_locations(self.domain)
        self.sto = locations['STO']
        self.sto.metadata = {
            'nikshay_code': 'MH',
        }
        self.sto.save()

        self.dto = locations['DTO']
        self.dto.metadata = {
            'nikshay_code': 'ABD',
        }
        self.dto.save()

        self.drtb_hiv = locations['DRTB-HIV']
        self.drtb_hiv.save()

        self.tu = locations['TU']
        self.tu.metadata = {
            'nikshay_code': '1',
        }
        self.tu.save()

        self.phi = locations['PHI']
        self.phi.metadata = {
            'nikshay_code': '2',
        }
        self.phi.save()
        super(ENikshayLocationStructureMixin, self).setUp()

    def tearDown(self):
        self.project.delete()
        SQLLocation.objects.all().delete()
        LocationType.objects.all().delete()
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

    def _setup_enikshay_locations(self, domain_name):
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
                        ])
                    ]),
                    LocationStructure('DRTB', 'drtb', []),
                    LocationStructure('CDST', 'cdst', []),
                ])
            ])
        ]

        setup_location_types_with_structure(domain_name, location_type_structure)
        return setup_locations_with_structure(domain_name, location_structure)
