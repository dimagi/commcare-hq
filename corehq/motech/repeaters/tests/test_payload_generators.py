import json
import random
import string
from datetime import datetime
from decimal import Decimal
from typing import Tuple
from uuid import uuid4

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.repeater_helpers import (
    get_relevant_case_updates_from_form_json,
)
from corehq.motech.repeaters.repeater_generators import (
    BasePayloadGenerator,
    FormDictPayloadGenerator,
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])


class TestDataTypes(TestCase, DomainSubscriptionMixin):
    """
    Test that data types returned by FormDictPayloadGenerator match
    those returned by FormRepeaterJsonPayloadGenerator.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        xform_id = uuid4().hex
        case_id = uuid4().hex
        post_xform(xform_id, case_id)
        cls.form = FormAccessors(DOMAIN).get_form(xform_id)

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def test_form_json_decimal(self):
        """
        When a decimal is taken from form JSON or a case block, it is a
        ``str``. When it is taken from a case property, it is a ``Decimal``.
        """
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        # Test value from form_json
        self.assertIsInstance(form_dict['form']['decimal'], str)
        self.assertIsInstance(info.form_question_values['/data/decimal'], str)
        # Test value from case block
        self.assertIsInstance(info.updates['decimal'], str)
        # Test value from case property
        self.assertIsInstance(info.extra_fields['decimal'], Decimal)  # <--

    def test_form_dict_decimal(self):
        """
        When a decimal is taken from form JSON or a case block, it is a
        ``str``. When it is taken from a case property, it is a ``Decimal``.
        """
        gen = FormDictPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['decimal'], str)
        self.assertIsInstance(info.form_question_values['/data/decimal'], str)
        self.assertIsInstance(info.updates['decimal'], str)
        self.assertIsInstance(info.extra_fields['decimal'], Decimal)  # <--

    def test_form_json_integer(self):
        """
        When an integer is taken from form JSON or a case block, it is a
        ``str``. When it is taken from a case property, it is still a ``str``.
        """
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['year'], str)
        self.assertIsInstance(info.form_question_values['/data/year'], str)
        self.assertIsInstance(info.updates['year'], str)
        self.assertIsInstance(info.extra_fields['year'], str)  # <--

    def test_form_dict_integer(self):
        """
        When an integer is taken from form JSON or a case block, it is a
        ``str``. When it is taken from a case property, it is still a ``str``.
        """
        gen = FormDictPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['year'], str)
        self.assertIsInstance(info.form_question_values['/data/year'], str)
        self.assertIsInstance(info.updates['year'], str)
        self.assertIsInstance(info.extra_fields['year'], str)  # <--

    def test_form_json_multiplechoice(self):
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['breakfast'], str)
        self.assertIsInstance(info.form_question_values['/data/breakfast'], str)
        self.assertIsInstance(info.updates['breakfast'], str)
        self.assertIsInstance(info.extra_fields['breakfast'], str)

    def test_form_dict_multiplechoice(self):
        gen = FormDictPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['breakfast'], str)
        self.assertIsInstance(info.form_question_values['/data/breakfast'], str)
        self.assertIsInstance(info.updates['breakfast'], str)
        self.assertIsInstance(info.extra_fields['breakfast'], str)

    def get_payload_info(
        self,
        payload_generator: BasePayloadGenerator,
    ) -> Tuple[dict, CaseTriggerInfo]:
        payload = payload_generator.get_payload(None, self.form)
        if isinstance(payload, str):
            payload = json.loads(payload)
        [info] = get_relevant_case_updates_from_form_json(
            DOMAIN,
            payload,
            case_types=None,
            extra_fields=['year', 'breakfast', 'decimal'],
            form_question_values=get_form_question_values(payload),
        )
        return payload, info


def post_xform(xform_id, case_id):
    user_id = uuid4().hex
    now_str = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
    xform = f"""<?xml version='1.0' ?>
<data xmlns="https://commcarehq.org/test/TestDataTypes/">

    <name>spam</name>
    <year>1970</year>
    <breakfast>spam egg spam spam bacon spam</breakfast>
    <decimal>4.4</decimal>

    <ctx:case case_id="{case_id}"
              date_modified="{now_str}"
              user_id="{user_id}"
              xmlns:ctx="http://commcarehq.org/case/transaction/v2">
      <ctx:create>
        <ctx:case_type>sketch</ctx:case_type>
        <ctx:case_name>spam</ctx:case_name>
        <ctx:owner_id>{user_id}</ctx:owner_id>
      </ctx:create>
      <ctx:update>
        <ctx:year>1970</ctx:year>
        <ctx:breakfast>spam egg spam spam bacon spam</ctx:breakfast>
        <ctx:decimal>4.4</ctx:decimal>
      </ctx:update>
    </ctx:case>

    <jrm:meta xmlns:jrm="http://commcarehq.org/jr/xforms">
        <jrm:deviceID>TestDataTypes</jrm:deviceID>
        <jrm:timeStart>{now_str}</jrm:timeStart>
        <jrm:timeEnd>{now_str}</jrm:timeEnd>
        <jrm:username>admin</jrm:username>
        <jrm:userID>testy.mctestface</jrm:userID>
        <jrm:instanceID>{xform_id}</jrm:instanceID>
    </jrm:meta>
</data>
"""
    submit_form_locally(xform, DOMAIN)
