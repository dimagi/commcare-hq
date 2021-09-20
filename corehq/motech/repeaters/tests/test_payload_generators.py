"""
These tests were written to check that FormDictPayloadGenerator behaved
like FormRepeaterJsonPayloadGenerator.
"""
import json
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

SQL_DOMAIN = 'test-sql-domain'


class TestSqlDataTypes(TestCase):
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
        cls.domain_obj.delete()
        super().tearDownClass()

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

        form_json_gen = FormRepeaterJsonPayloadGenerator(None)
        cls.form_json_payload_info = cls.get_payload_info(form_json_gen)

        form_dict_gen = FormDictPayloadGenerator(None)
        cls.form_dict_payload_info = cls.get_payload_info(form_dict_gen)

    @classmethod
    def get_payload_info(
        cls,
        payload_generator: BasePayloadGenerator,
    ) -> Tuple[dict, CaseTriggerInfo]:

        payload = payload_generator.get_payload(None, cls.form)
        if isinstance(payload, str):
            payload = json.loads(payload)
        [info] = get_relevant_case_updates_from_form_json(
            cls.domain,
            payload,
            case_types=None,
            extra_fields=list(cls.case_update.keys()),
            form_question_values=get_form_question_values(payload),
        )
        return payload, info

    def test_string_values_in_common(self):
        for (payload, info), question, expected_type in [
            (self.form_json_payload_info, 'year', str),
            (self.form_dict_payload_info, 'year', str),

            (self.form_json_payload_info, 'breakfast', str),
            (self.form_dict_payload_info, 'breakfast', str),
        ]:
            self.check_payload_info_type(payload, info, question, expected_type)

    def check_payload_info_type(self, payload, info, question, expected_type):
        self.assertIsInstance(payload['form'][question], str)
        self.assertIsInstance(info.form_question_values[f'/data/{question}'], str)
        self.assertIsInstance(info.updates[question], str)
        self.assertIsInstance(info.extra_fields[question], expected_type)

    def test_string_values_in_sql(self):
        for (payload, info), question, expected_type in [
            (self.form_json_payload_info, 'price', str),
            (self.form_dict_payload_info, 'price', str),

            (self.form_json_payload_info, 'album_release', str),
            (self.form_dict_payload_info, 'album_release', str),

            (self.form_json_payload_info, 'breakfast_oclock', str),
            (self.form_dict_payload_info, 'breakfast_oclock', str),

            (self.form_json_payload_info, 'breakfast_exactly', str),
            (self.form_dict_payload_info, 'breakfast_exactly', str),
        ]:
            self.check_payload_info_type(payload, info, question, expected_type)


def create_sql_domain(name):
    return Domain.get_or_create_with_name(
        name,
        is_active=True,
        secure_submissions=False,
    )
