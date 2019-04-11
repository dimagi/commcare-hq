from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from django.test.testcases import TestCase

from custom.aaa.dbaccessors import EligibleCoupleQueryHelper
from custom.aaa.models import Child, Woman, WomanHistory
from six.moves import range


class TestEligibleCoupleBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestEligibleCoupleBeneficiarySections, cls).setUpClass()
        cls.woman = Woman.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            opened_on='2019-01-01',
        )

    @classmethod
    def tearDownClass(cls):
        Woman.objects.all().delete()
        super(TestEligibleCoupleBeneficiarySections, cls).tearDownClass()

    @property
    def helper(self):
        return EligibleCoupleQueryHelper(self.domain, 'person_case_id', date(2019, 3, 31))

    def test_eligible_couple_details_no_history(self):
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })

    def test_eligible_couple_details_with_history(self):
        history = WomanHistory.objects.create(
            person_case_id='person_case_id',
            fp_current_method_history=[
                ['2019-01-01', 'iud'],
                ['2019-04-01', 'future stuff'],
                ['2018-08-01', 'pill'],
                ['2019-03-01', 'condom'],
            ]
        )
        self.addCleanup(history.delete)
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'condom',
                'familyPlanningMethodDate': date(2019, 3, 1),
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'iud',
                'preferredFamilyPlaningMethod': 'N/A',
            })

    def test_eligible_couple_details_with_male_children(self):
        child = Child.objects.create(
            opened_on='2019-01-01',
            person_case_id='case_id',
            child_health_case_id='case_id',
            mother_case_id='person_case_id',
            sex='M'
        )
        self.addCleanup(child.delete)
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 1,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 1,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })
        for i in range(3):
            child = Child.objects.create(
                opened_on='2019-01-01',
                person_case_id='case_id{}'.format(i),
                child_health_case_id='case_id{}'.format(i),
                mother_case_id='person_case_id',
                sex='M'
            )
            self.addCleanup(child.delete)
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 4,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 4,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })

        Woman.objects.filter(person_case_id=self.woman.person_case_id).update(num_male_children_died='4')
        self.addCleanup(lambda: (
            Woman.objects
            .filter(person_case_id=self.woman.person_case_id)
            .update(num_male_children_died=None)
        ))
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 8,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 4,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })

    def test_eligible_couple_details_with_female_children(self):
        child = Child.objects.create(
            opened_on='2019-01-01',
            person_case_id='case_id',
            child_health_case_id='case_id',
            mother_case_id='person_case_id',
            sex='F'
        )
        self.addCleanup(child.delete)
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 1,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 1,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })
        for i in range(3):
            child = Child.objects.create(
                opened_on='2019-01-01',
                person_case_id='case_id{}'.format(i),
                child_health_case_id='case_id{}'.format(i),
                mother_case_id='person_case_id',
                sex='F'
            )
            self.addCleanup(child.delete)
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 4,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 4,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })

        Woman.objects.filter(person_case_id=self.woman.person_case_id).update(num_female_children_died='4')
        self.addCleanup(lambda: (
            Woman.objects
            .filter(person_case_id=self.woman.person_case_id)
            .update(num_female_children_died=None)
        ))
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 8,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 4,
                'familyPlaningMethod': 'N/A',
                'familyPlanningMethodDate': 'N/A',
                'ashaVisit': 'N/A',
                'previousFamilyPlanningMethod': 'N/A',
                'preferredFamilyPlaningMethod': 'N/A',
            })


class TestEligibleCoupleBeneficiaryList(TestCase):
    domain = 'reach-test'

    def tearDown(self):
        Woman.objects.all().delete()
        super(TestEligibleCoupleBeneficiaryList, self).tearDown()

    def _create_woman(self, dob, marital_status='married', migration_status=None, pregnant_ranges=None):
        Woman.objects.create(
            person_case_id='_id',
            domain=self.domain,
            dob=dob,
            opened_on='2019-01-01',
            migration_status=migration_status,
            marital_status=marital_status,
            pregnant_ranges=pregnant_ranges,
        )

    def test_fourteen_year_old(self):
        self._create_woman('2005-01-01')
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_fifteen_year_old(self):
        self._create_woman('2004-01-01')
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 1)

    def test_49_year_old(self):
        self._create_woman('1970-12-01')
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 1)

    def test_50_year_old(self):
        self._create_woman('1970-1-1')
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_migrated_49_year_old(self):
        self._create_woman('1970-12-01', migration_status='yes')
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_unmarried_49_year_old(self):
        self._create_woman('1970-12-01', marital_status=None)
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_previously_pregnant(self):
        self._create_woman('1990-12-01', pregnant_ranges=[['2010-01-01', '2010-10-01']])
        self.assertEqual(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 1)
