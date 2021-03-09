"""
These tests were written to check that FormDictPayloadGenerator behaved
like FormRepeaterJsonPayloadGenerator, but they revealed something I did
not expect about Decimal case properties when using a Couch backend.

TL;DR? Skip to TestCouchDataTypes.test_form_json_decimal.

"""
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Tuple
from uuid import uuid4

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils.xform import FormSubmissionBuilder
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

COUCH_DOMAIN = 'test-couch-domain'
SQL_DOMAIN = 'test-sql-domain'


class DataTypesBase:

    @classmethod
    def set_up_form(cls):
        cls.form_id = uuid4().hex
        user_id = uuid4().hex
        cls.case_update = {
            'year': '1970',
            'breakfast': 'spam egg spam spam bacon spam',
            'price': '2.40',
            'album_release': '1972-09-08',
            'breakfast_oclock': '09:00:00',
            'breakfast_exactly': '1972-09-08T09:00:00.000Z',
        }
        builder = FormSubmissionBuilder(
            form_id=cls.form_id,
            form_properties={
                'name': 'spam',
                **cls.case_update,
            },
            case_blocks=[CaseBlock(
                case_id=uuid4().hex,
                create=True,
                case_type='sketch',
                case_name='spam',
                owner_id=user_id,
                update=cls.case_update
            )],
            metadata=TestFormMetadata(
                domain=cls.domain,
                user_id=user_id,
            ),
        )
        submit_form_locally(builder.as_xml_string(), cls.domain)
        cls.form = FormAccessors(cls.domain).get_form(cls.form_id)

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
        self.assertIsInstance(info.extra_fields['year'], str)

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
        self.assertIsInstance(info.extra_fields['year'], str)

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
            self.domain,
            payload,
            case_types=None,
            extra_fields=list(self.case_update.keys()),
            form_question_values=get_form_question_values(payload),
        )
        return payload, info


class TestCouchDataTypes(TestCase, DataTypesBase):
    """
    Test that data types returned by FormDictPayloadGenerator match
    those returned by FormRepeaterJsonPayloadGenerator when using a
    Couch backend.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = COUCH_DOMAIN
        cls.domain_obj = create_couch_domain(COUCH_DOMAIN)
        cls.set_up_form()

    def test_form_json_decimal(self):
        """
        When a decimal is taken from form JSON or a case block, it is a
        ``str``. When it is taken from a case property, it is a ``Decimal``.

        This only happens when using a Couch backend. Strings are
        converted by `jsonobject`_.

        .. _jsonobject: https://github.com/dimagi/commcare-hq/blob/9634efa3905/corehq/ex-submodules/dimagi/ext/jsonobject.py#L94-L99

        """
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        # Test value from form_json
        self.assertIsInstance(form_dict['form']['price'], str)
        self.assertIsInstance(info.form_question_values['/data/price'], str)
        # Test value from case block
        self.assertIsInstance(info.updates['price'], str)
        # Test value from case property
        self.assertIsInstance(info.extra_fields['price'], Decimal)

    def test_form_dict_decimal(self):
        gen = FormDictPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(form_dict['form']['price'], str)
        self.assertIsInstance(info.form_question_values['/data/price'], str)
        self.assertIsInstance(info.updates['price'], str)
        self.assertIsInstance(info.extra_fields['price'], Decimal)

    def test_form_json_date(self):
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)
        self.assertIsInstance(info.updates['album_release'], str)
        self.assertIsInstance(info.extra_fields['album_release'], date)

    def test_form_json_time(self):
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)
        self.assertIsInstance(info.updates['breakfast_oclock'], str)
        self.assertIsInstance(info.extra_fields['breakfast_oclock'], time)

    def test_form_json_datetime(self):
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)
        self.assertIsInstance(info.updates['breakfast_exactly'], str)
        self.assertIsInstance(info.extra_fields['breakfast_exactly'], datetime)


class TestSqlDataTypes(TestCase, DataTypesBase):
    """
    Test that data types returned by FormDictPayloadGenerator match
    those returned by FormRepeaterJsonPayloadGenerator when using a SQL
    backend.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = SQL_DOMAIN
        cls.domain_obj = create_sql_domain(SQL_DOMAIN)
        cls.set_up_form()

    @classmethod
    def tearDownClass(cls):
        FormAccessorSQL.hard_delete_forms(SQL_DOMAIN, [cls.form_id])
        super().tearDownClass()

    def test_form_json_decimal(self):
        """
        Case properties of CommCareCaseSQL behave as you would expect.
        """
        gen = FormRepeaterJsonPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        # Test value from case block
        self.assertIsInstance(info.updates['price'], str)
        # Test value from case property
        self.assertIsInstance(info.extra_fields['price'], str)

    def test_form_dict_decimal(self):
        gen = FormDictPayloadGenerator(None)
        form_dict, info = self.get_payload_info(gen)

        self.assertIsInstance(info.updates['price'], str)
        self.assertIsInstance(info.extra_fields['price'], str)


def create_couch_domain(name):
    return Domain.get_or_create_with_name(
        name,
        is_active=True,
        secure_submissions=False,
        use_sql_backend=False,
    )


def create_sql_domain(name):
    return Domain.get_or_create_with_name(
        name,
        is_active=True,
        secure_submissions=False,
        use_sql_backend=True,
    )
