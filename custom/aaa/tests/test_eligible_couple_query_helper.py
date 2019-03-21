from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import TestCase

from custom.aaa.dbaccessors import EligibleCoupleQueryHelper
from custom.aaa.models import Woman


class TestEligibleCoupleBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestEligibleCoupleBeneficiarySections, cls).setUpClass()
        Woman.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            opened_on='2019-01-01',
        )

    @classmethod
    def tearDownClass(cls):
        Woman.objects.all().delete()
        super(TestEligibleCoupleBeneficiarySections, cls).tearDownClass()

    def test_eligible_couple_details(self):
        self.assertEqual(
            EligibleCoupleQueryHelper(self.domain, 'person_case_id').eligible_couple_details(),
            {
                'maleChildrenBorn': 'N/A',
                'femaleChildrenBorn': 'N/A',
                'maleChildrenAlive': 'N/A',
                'femaleChildrenAlive': 'N/A',
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })
