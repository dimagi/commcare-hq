from django.test import TestCase, override_settings

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.domain.models import Domain

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.tests.utils import (
    setup_enikshay_locations,
    get_person_case_structure,
    get_occurrence_case_structure,
    get_episode_case_structure,
    get_test_case_structure,
    get_referral_case_structure,
    get_trail_case_structure,
)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCreateEnikshayCases(TestCase):
    domain = 'enikshay-2b-migration'

    def setUp(self):
        self.project = Domain(name=self.domain)
        self.project.save()
        self.location_types, self.locations = setup_enikshay_locations(self.domain)
        self.factory = CaseFactory(domain=self.domain)
        self.cases = self.setup_cases()

    def tearDown(self):
        self.project.delete()

    def setup_cases(self):
        person = self._get_person_structure('roland-deschain', self.locations['DTO'].location_id)
        occurrence = self._get_occurrence_structure(person)
        episode = self._get_episode_structure(occurrence)
        test = self._get_test_structure(occurrence)
        referral = self._get_referral_structure(person)
        trail = self._get_trail_structure(referral)
        return {c.case_id: c for c in self.factory.create_or_update_cases([
            episode, test, referral, trail
        ])}

    def _get_person_structure(self, person_id, owner_id):
        person_fields = {ENROLLED_IN_PRIVATE: ""}
        person = get_person_case_structure(person_id, owner_id, extra_update=person_fields)
        person.attrs['owner_id'] = owner_id
        return person

    def _get_occurrence_structure(self, person):
        case_id = person.case_id + '-occurrence'
        return get_occurrence_case_structure(case_id, person)

    def _get_episode_structure(self, occurrence):
        case_id = occurrence.case_id + '-episode'
        return get_episode_case_structure(case_id, occurrence)

    def _get_test_structure(self, occurrence):
        case_id = occurrence.case_id + '-test'
        return get_test_case_structure(case_id, occurrence.case_id)

    def _get_referral_structure(self, person):
        case_id = person.case_id + '-referral'
        return get_referral_case_structure(case_id, person.case_id)

    def _get_trail_structure(self, referral):
        case_id = referral.case_id + '-trail'
        trail = get_trail_case_structure(case_id, "overriding this anyways")
        trail.indices = [CaseIndex(
            CaseStructure(case_id=referral.case_id, attrs={"create": False}),
            identifier='parent',
            relationship=CASE_INDEX_CHILD,
            related_type='occurrence',
        )]
        return trail