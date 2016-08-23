from datetime import datetime

from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.const import CASE_INDEX_EXTENSION


class ENikshayCaseStructureMixin(object):
    def setUp(self):
        super(ENikshayCaseStructureMixin, self).setUp()
        self.domain = getattr(self, 'domain', 'fake-domain-from-mixin')
        self.factory = CaseFactory(domain=self.domain)

        self.person_id = u"person"
        self.occurrence_id = u"occurrence"
        self.episode_id = u"episode"

    def create_case_structure(self):
        person = CaseStructure(
            case_id=self.person_id,
            attrs={
                "case_type": "person",
                "create": True,
                "update": dict(
                    name="Pippin",
                    aadhaar_number="499118665246",
                    mobile_number="0123456789",
                    backup_number="0999999999",
                    dob="1987-08-15",
                )
            },
        )
        occurrence = CaseStructure(
            case_id=self.occurrence_id,
            attrs={
                'create': True,
                'case_type': 'occurrence',
                "update": dict(
                    name="Occurrence #1",
                )
            },
            indices=[CaseIndex(
                person,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=person.attrs['case_type'],
            )],
        )
        episode = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    person_name="Pippin",
                    opened_on=datetime(1989, 6, 11, 0, 0),
                    patient_type="new",
                    hiv_status="reactive",
                    episode_type="confirmed_tb",
                    default_adherence_confidence="high",
                )
            },
            indices=[CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence.attrs['case_type'],
            )],
        )
        return {case.case_id: case for case in self.factory.create_or_update_cases([episode])}

    def create_adherence_cases(self, adherence_dates):
        return self.factory.create_or_update_cases([
            CaseStructure(
                case_id=adherence_date.strftime('%Y-%m-%d'),
                attrs={
                    "case_type": "adherence",
                    "create": True,
                    "update": {
                        "name": adherence_date,
                        "adherence_value": "unobserved_dose",
                        "adherence_source": "99DOTS",
                        "adherence_date": adherence_date,
                        "person_name": "Pippin",
                        "adherence_confidence": "medium",
                        "shared_number_99_dots": False,
                    },
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=self.episode_id, attrs={"create": False}),
                    identifier='host',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type='episode',
                )],
                walk_related=False,
            )
            for adherence_date in adherence_dates
        ])
