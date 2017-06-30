import uuid
from casexml.apps.case.mock import CaseBlock
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.hqcase.utils import submit_case_blocks, update_case
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from custom.icds.messaging.custom_content import static_negative_growth_indicator, GROWTH_MONITORING_XMLNS
from django.test import TestCase
from xml.etree import ElementTree


TEST_GROWTH_FORM_XML = """<?xml version="1.0" ?>
<data xmlns="{xmlns}">
    <weight_prev>{weight_prev}</weight_prev>
    <weight_child>{weight_child}</weight_child>
    <case case_id="{case_id}" xmlns="http://commcarehq.org/case/transaction/v2">
        <update>
            <weight_child>{weight_child}</weight_child>
        </update>
    </case>
</data>
"""


def submit_growth_form(domain, case_id, weight_prev, weight_child):
    xml = TEST_GROWTH_FORM_XML.format(
        xmlns=GROWTH_MONITORING_XMLNS,
        case_id=case_id,
        weight_prev=weight_prev,
        weight_child=weight_child,
    )
    submit_form_locally(xml, domain)


@use_sql_backend
class CustomContentTest(TestCase):
    domain = 'icds-custom-content-test'

    @classmethod
    def setUpClass(cls):
        super(CustomContentTest, cls).setUpClass()
        cls.mother_person_case = cls.create_case('person')
        cls.child_person_case = cls.create_case(
            'person',
            cls.mother_person_case.case_id,
            cls.mother_person_case.type,
            'mother',
            'child',
            case_name="Joe"
        )
        cls.child_health_extension_case = cls.create_case(
            'child_health',
            cls.child_person_case.case_id,
            cls.child_person_case.type,
            'parent',
            'extension'
        )

        update_case(
            cls.domain,
            cls.mother_person_case.case_id,
            {'language_code': 'en'},
        )

        cls.mother_person_case = CaseAccessors(cls.domain).get_case(cls.mother_person_case.case_id)

    @classmethod
    def tearDownClass(cls):
        CaseAccessorSQL.hard_delete_cases(
            cls.domain,
            [
                cls.mother_person_case.case_id,
                cls.child_person_case.case_id,
                cls.child_health_extension_case.case_id,
            ]
        )
        super(CustomContentTest, cls).tearDownClass()

    @classmethod
    def create_case(cls, case_type, parent_case_id=None, parent_case_type=None, parent_identifier=None,
            parent_relationship=None, case_name=None):

        kwargs = {}
        if parent_case_id:
            kwargs['index'] = {parent_identifier: (parent_case_type, parent_case_id, parent_relationship)}

        if case_name:
            kwargs['case_name'] = case_name

        caseblock = CaseBlock(
            uuid.uuid4().hex,
            case_type=case_type,
            create=True,
            **kwargs
        )
        return submit_case_blocks(ElementTree.tostring(caseblock.as_xml()), cls.domain)[1][0]

    def test_static_negative_growth_indicator(self):
        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.child_health_extension_case.case_id,
        )

        # Test when current weight is greater than previous
        submit_growth_form(self.domain, self.child_health_extension_case.case_id, '10.1', '10.4')
        self.assertEqual(
            static_negative_growth_indicator(self.mother_person_case, schedule_instance),
            []
        )

        # Test when current weight is equal to previous
        submit_growth_form(self.domain, self.child_health_extension_case.case_id, '10.1', '10.1')
        self.assertEqual(
            static_negative_growth_indicator(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has remained static in the last "
             "month. Please consult your AWW for necessary advice."]
        )

        # Test when current weight is less than previous
        submit_growth_form(self.domain, self.child_health_extension_case.case_id, '10.1', '9.9')
        self.assertEqual(
            static_negative_growth_indicator(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has reduced in the last month. "
             "Please consult your AWW for necessary advice."]
        )

        # Test ignoring forms with the wrong xmlns
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value1'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value2'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value3'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value4'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value5'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value6'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value7'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value8'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value9'})
        update_case(self.domain, self.child_health_extension_case.case_id, {'property': 'value10'})

        self.assertEqual(
            static_negative_growth_indicator(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has reduced in the last month. "
             "Please consult your AWW for necessary advice."]
        )
