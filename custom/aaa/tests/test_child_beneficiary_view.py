from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import TestCase

from custom.aaa.dbaccessors import ChildQueryHelper
from custom.aaa.models import Child


class TestChildBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestChildBeneficiarySections, cls).setUpClass()
        Child.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            child_health_case_id='child_health_case_id',
            opened_on='2019-01-01'
        )

    @classmethod
    def tearDownClass(cls):
        Child.objects.all().delete()
        super(TestChildBeneficiarySections, cls).tearDownClass()

    def test_child_infant_section(self):
        self.assertDictEqual(
            ChildQueryHelper(self.domain, 'person_case_id').infant_details(),
            {
                'breastfeedingInitiated': None,
                'dietDiversity': None,
                'birthWeight': None,
                'dietQuantity': None,
                'breastFeeding': None,
                'handwash': None,
                'exclusivelyBreastfed': None,
                'babyCried': None,
                'pregnancyLength': 'N/A',
            })

