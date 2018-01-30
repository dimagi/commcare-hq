from __future__ import absolute_import
from django.test import TestCase, override_settings

from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import get_first_parent_of_case, CASE_TYPE_DRTB_HIV_REFERRAL
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
from .management.commands.enikshay_2b_case_properties import ENikshay2BMigrator


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
        private_person = self._get_person_structure('susanna-dean', self.locations['PHI'].location_id)
        private_person.attrs['update'][ENROLLED_IN_PRIVATE] = 'true'  # should be excluded
        person = self._get_person_structure('roland-deschain', self.locations['PHI'].location_id)
        occurrence = self._get_occurrence_structure(person)
        episode = self._get_episode_structure(occurrence)
        test = self._get_test_structure(occurrence)
        referral = self._get_referral_structure(person)
        trail = self._get_trail_structure(referral)
        drtb_hiv_referral = self._get_drtb_hiv_referral_structure(episode)
        cases = {c.case_id: c for c in self.factory.create_or_update_cases([
            private_person, occurrence, test, referral, episode, trail, drtb_hiv_referral,
        ])}
        cases[test.case_id] = self._update_test(test)
        return cases

    def _get_person_structure(self, person_id, owner_id):
        person_fields = {ENROLLED_IN_PRIVATE: ""}
        person = get_person_case_structure(person_id, owner_id, extra_update=person_fields)
        person.attrs['owner_id'] = owner_id
        person.attrs['update'].update({
            'person_id': 'person_id',
            'phi_area': 'phi_area',
            'date_referred_out': 'date_referred_out',
            'referred_by_id': 'referred_by_id',
            'phone_number': '1234567890',
        })
        return person

    def _get_occurrence_structure(self, person):
        case_id = person.case_id + '-occurrence'
        return get_occurrence_case_structure(case_id, person)

    def _get_episode_structure(self, occurrence):
        case_id = occurrence.case_id + '-episode'
        episode = get_episode_case_structure(case_id, occurrence)
        episode.attrs['update'].update({
            'episode_type': "confirmed_tb",
            'alcohol_history': "alcohol_history",
            'alcohol_deaddiction': "alcohol_deaddiction",
            'tobacco_user': "tobacco_user",
            'occupation': "occupation",
            'phone_number_other': "phone_number_other",
            'disease_classification': 'disease_classification',
            'site_choice': 'site_choice',
            'site_detail': 'site_detail',
            'key_population_status': 'key_population_status',
            'key_populations': 'key_populations',
            'treatment_status': 'second_line_treatment',
            'date_of_diagnosis': '',
            'date_reported': 'date_reported',
            'full_dosage': 'full_dosage',
            'test_confirming_diagnosis': 'chest_x-ray',
        })
        return episode

    def _get_test_structure(self, occurrence):
        case_id = occurrence.case_id + '-test'
        test = get_test_case_structure(case_id, occurrence.case_id)
        test.attrs['update'].update({
            'diagnostic_drtb_test_reason': 'diagnostic_drtb_test_reason',
            'follow_up_test_reason': 'definitely_not_private_ntm',
            'diagnostic_test_reason': 'diagnostic_test_reason',
            'purpose_of_testing': 'diagnostic',
            'max_bacilli_count': '11',
            'clinical_remarks': 'that looks infected',
            'result': 'tb_detected',
            'test_type_value': 'cbnaat',
        })
        return test

    def _update_test(self, test):
        form_xml = """
        <data xmlns="http://commcarehq.org/case">
            <case case_id="{case_id}"
                  xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <result_recorded>yes</result_recorded>
                </update>
            </case>
            <update_test_result>
                <cbnaat>
                    <ql_sample_a>
                        <sample_a_rif_resistance_result>detected</sample_a_rif_resistance_result>
                    </ql_sample_a>
                </cbnaat>
            </update_test_result>
        </data>
        """.format(case_id=test.case_id)
        submit_form_locally(form_xml, self.domain)

    def _get_referral_structure(self, person):
        case_id = person.case_id + '-referral'
        referral = get_referral_case_structure(case_id, person.case_id)
        referral.attrs['update'].update({
            'referral_date': 'referral_date',
            'referred_to_location_name': 'referred_to_location_name',
            'reason_for_refusal_other_detail': 'reason_for_refusal_other_detail',
            'reason_for_refusal': 'reason_for_refusal',
            'acceptance_refusal_date': 'acceptance_refusal_date',
            'phi': 'phi',
        })
        return referral

    def _get_trail_structure(self, referral):
        case_id = referral.case_id + '-trail'
        trail = get_trail_case_structure(case_id, "overriding this anyways")
        trail.indices = [CaseIndex(
            CaseStructure(case_id=referral.case_id, attrs={"create": False}),
            identifier='parent',
            relationship=CASE_INDEX_CHILD,
            related_type='referral',
        )]
        return trail

    def _get_drtb_hiv_referral_structure(self, episode):
        return CaseStructure(
            case_id=episode.case_id + '-drtb_hiv_referral',
            attrs={
                "case_type": CASE_TYPE_DRTB_HIV_REFERRAL,
                "owner_id": "drtb_hiv_referral_owner",
                "create": True,
                "update": {},
            },
            indices=[CaseIndex(
                CaseStructure(case_id=episode.case_id, attrs={"create": False}),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type='episode',
            )],
            walk_related=False,
        )

    def test(self):
        migrator = ENikshay2BMigrator(self.domain, commit=True)
        # first check some utils
        person_case_ids = migrator.get_relevant_person_case_ids()
        person_case_sets = list(migrator.get_relevant_person_case_sets(person_case_ids))
        self.assertEqual(1, len(person_case_sets))
        person = person_case_sets[0]

        self.assertEqual('roland-deschain', person.person.case_id)
        self.assertItemsEqual(['roland-deschain-occurrence'], [c.case_id for c in person.occurrences])
        self.assertItemsEqual(['roland-deschain-occurrence-episode'], [c.case_id for c in person.episodes])
        self.assertItemsEqual(['roland-deschain-occurrence-test'], [c.case_id for c in person.tests])
        self.assertItemsEqual(['roland-deschain-referral'], [c.case_id for c in person.referrals])
        self.assertItemsEqual(['roland-deschain-referral-trail'], [c.case_id for c in person.trails])
        self.assertItemsEqual(['roland-deschain-occurrence-episode-drtb_hiv_referral'],
                              [c.case_id for c in person.drtb_hiv])

        # run the actual migration
        migrator.migrate()

        # check the results
        accessor = CaseAccessors(self.domain)
        new_person = accessor.get_case(person.person.case_id)
        self.assertDictContainsSubset({
            'area': 'phi_area',
            'referred_outside_enikshay_date': 'date_referred_out',
            'referred_outside_enikshay_by_id': 'referred_by_id',
            'contact_phone_number': '911234567890',
            'current_episode_type': "confirmed_tb",
            'alcohol_history': "alcohol_history",
            'alcohol_deaddiction': "alcohol_deaddiction",
            'tobacco_user': "tobacco_user",
            'occupation': "occupation",
            'phone_number_other': "phone_number_other",
            'phi_name': 'PHI',
            'tu_name': 'TU',
            'tu_id': self.locations['TU'].location_id,
            'dto_name': 'DTO',
            'dto_id': self.locations['DTO'].location_id,
            'dataset': 'real',
            'updated_by_migration': 'enikshay_2b_case_properties',
        }, new_person.dynamic_case_properties())

        new_occurrence = accessor.get_case(person.occurrences[0].case_id)
        self.assertDictContainsSubset({
            'current_episode_type': 'confirmed_tb',
            'disease_classification': 'disease_classification',
            'site_choice': 'site_choice',
            'site_detail': 'site_detail',
            'key_population_status': 'key_population_status',
            'key_populations': 'key_populations',
        }, new_occurrence.dynamic_case_properties())

        new_episode = accessor.get_case(person.episodes[0].case_id)
        self.assertDictContainsSubset({
            'treatment_status': 'initiated_second_line_treatment',
            'date_of_diagnosis': 'date_reported',
            'dosage_display': 'full_dosage',
            'dosage_summary': 'full_dosage',
            'rft_general': 'diagnosis_dstb',
            'diagnosis_test_type': 'chest_x-ray',
            'diagnosis_test_type_label': "Chest X-ray",
            'is_active': 'yes',
        }, new_episode.dynamic_case_properties())

        new_test = accessor.get_case(person.tests[0].case_id)
        self.assertDictContainsSubset({
            'is_direct_test_entry': 'no',
            'rft_drtb_diagnosis': 'diagnostic_drtb_test_reason',
            'dataset': 'real',
            'rft_general': 'diagnosis_dstb',
            'rft_dstb_diagnosis': 'diagnostic_test_reason',
            'rft_dstb_followup': 'definitely_not_private_ntm',
            'episode_case_id': 'roland-deschain-occurrence-episode',
            'result_summary_display': "TB Detected\nR: Res\nCount of bacilli: 11\nthat looks infected",
            'drug_resistance_list': 'r',
        }, new_test.dynamic_case_properties())

        new_referral = accessor.get_case(person.referrals[0].case_id)
        self.assertDictContainsSubset({
            'referral_initiated_date': 'referral_date',
            'referred_to_name': 'referred_to_location_name',
            'referred_by_name': '',
            'referral_rejection_reason_other_detail': 'reason_for_refusal_other_detail',
            'referral_rejection_reason': 'reason_for_refusal',
            'referral_closed_date': 'acceptance_refusal_date',
            'accepted_by_name': 'phi',
        }, new_referral.dynamic_case_properties())
        parent = get_first_parent_of_case(self.domain, new_referral, 'occurrence')
        self.assertEqual(new_occurrence.case_id, parent.case_id)

        new_trail = accessor.get_case(person.trails[0].case_id)
        parent = get_first_parent_of_case(self.domain, new_trail, 'occurrence')
        self.assertEqual(new_occurrence.case_id, parent.case_id)

        new_drtb_hiv = accessor.get_case(person.drtb_hiv[0].case_id)
        self.assertTrue(new_drtb_hiv.closed)

        secondary_owner_id = accessor.get_case_ids_in_domain(type='secondary_owner')[0]
        new_secondary_owner = accessor.get_case(secondary_owner_id)
        self.assertEqual('person_id-drtb-hiv', new_secondary_owner.name)
        self.assertDictContainsSubset({
            'secondary_owner_type': 'drtb-hiv',
        }, new_secondary_owner.dynamic_case_properties())
        self.assertEqual("drtb_hiv_referral_owner", new_secondary_owner.owner_id)
        parent = get_first_parent_of_case(self.domain, new_secondary_owner, 'occurrence')
        self.assertEqual(new_occurrence.case_id, parent.case_id)
