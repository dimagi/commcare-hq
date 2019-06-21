from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from django.test.testcases import TestCase

from six.moves import range

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from custom.aaa.dbaccessors import EligibleCoupleQueryHelper
from custom.aaa.models import Child, Woman


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
        cls.adapters = []
        cls._init_table('reach-eligible_couple_forms')

    @classmethod
    def tearDownClass(cls):
        for adapter in cls.adapters:
            adapter.drop_table()
        Woman.objects.all().delete()
        super(TestEligibleCoupleBeneficiarySections, cls).tearDownClass()

    @classmethod
    def _get_adapter(cls, data_source_id):
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, data_source_id)
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        return get_indicator_adapter(datasource)

    @classmethod
    def _init_table(cls, data_source_id):
        adapter = cls._get_adapter(data_source_id)
        adapter.build_table()
        cls.adapters.append(adapter)
        return adapter

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
        add_preg_adapter = self._get_adapter('reach-eligible_couple_forms')
        self.addCleanup(add_preg_adapter.clear_table)
        for _id, _date, method in (
            ('ec_form_1', '2019-01-01', 'iud'),
            ('ec_form_2', '2019-04-01', 'future stuff'),
            ('ec_form_3', '2018-08-01', 'pill'),
            ('ec_form_4', '2019-03-01', 'condom'),
        ):
            add_preg_adapter.save({
                '_id': _id,
                'domain': self.domain,
                'doc_type': "XFormInstance",
                'xmlns': 'http://openrosa.org/formdesigner/21A52E12-3C84-4307-B680-1AB194FCE647',
                'form': {
                    "person_case_id": 'person_case_id',
                    "create_eligible_couple": {
                        "create_eligible_couple": {
                            "case": {
                                'update': {
                                    'fp_current_method': method,
                                }
                            },
                        },
                    },
                    "meta": {"timeEnd": _date},
                },
            })
        self.assertEqual(
            self.helper.eligible_couple_details(),
            {
                'maleChildrenBorn': 0,
                'femaleChildrenBorn': 0,
                'maleChildrenAlive': 0,
                'femaleChildrenAlive': 0,
                'familyPlaningMethod': 'condom',
                'familyPlanningMethodDate': date(2019, 3, 1),
                'ashaVisit': date(2019, 3, 1),
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

    @classmethod
    def setUpClass(cls):
        super(TestEligibleCoupleBeneficiaryList, cls).setUpClass()
        cls.adapters = []
        cls._init_table('reach-eligible_couple_forms')

    @classmethod
    def tearDownClass(cls):
        for adapter in cls.adapters:
            adapter.drop_table()
        super(TestEligibleCoupleBeneficiaryList, cls).tearDownClass()

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

    @classmethod
    def _get_adapter(cls, data_source_id):
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, data_source_id)
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        return get_indicator_adapter(datasource)

    @classmethod
    def _init_table(cls, data_source_id):
        adapter = cls._get_adapter(data_source_id)
        adapter.build_table()
        cls.adapters.append(adapter)
        return adapter

    def test_fourteen_year_old(self):
        self._create_woman('2005-01-01')
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 0)

    def test_fifteen_year_old(self):
        self._create_woman('2004-01-01')
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 1)

    def test_49_year_old(self):
        self._create_woman('1970-12-01')
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 1)

    def test_50_year_old(self):
        self._create_woman('1970-1-1')
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 0)

    def test_migrated_49_year_old(self):
        self._create_woman('1970-12-01', migration_status='migrated')
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 0)

    def test_unmarried_49_year_old(self):
        self._create_woman('1970-12-01', marital_status=None)
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 0)

    def test_previously_pregnant(self):
        self._create_woman('1990-12-01', pregnant_ranges=[['2010-01-01', '2010-10-01']])
        self.assertEqual(len(EligibleCoupleQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id')), 1)
