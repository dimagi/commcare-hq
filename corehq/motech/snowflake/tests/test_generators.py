import uuid
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.repeaters.repeater_generators import get_form_json_payload
from corehq.motech.snowflake.payload_generators import (
    FormJsonCsvPayloadGenerator,
)

DOMAIN = 'test-domain'


class TestFormJsonCsvPayloadGenerator(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        repeater = None  # unused
        cls.payload_generator = FormJsonCsvPayloadGenerator(repeater)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_get_payload(self):
        instance_id = str(uuid.uuid4())
        post_xform(instance_id)
        xform = FormAccessors(DOMAIN).get_form(instance_id)

        # Patch datetime so that `form_json` gets the same value for
        # "inserted_at"/"indexed_on" as `payload`.
        utcnow = datetime.utcnow()
        with patch('corehq.pillows.xform.datetime') as datetime_patch:
            datetime_patch.datetime.utcnow.return_value = utcnow
            repeat_record = object()
            payload = self.payload_generator.get_payload(repeat_record, xform)

            form_json = get_form_json_payload(xform)
        form_json_escaped = form_json.replace('"', '""')
        expected_csv = (
            f'{DOMAIN},'
            f'{xform.form_id},'
            f'{xform.received_on.isoformat(sep=" ")},'
            f'"{form_json_escaped}"\r\n'
        )
        self.assertEqual(payload, expected_csv)

    def test_content_type(self):
        self.assertEqual(self.payload_generator.content_type, 'text/csv')


def post_xform(instance_id, **kwargs):
    xform = f"""<?xml version='1.0' ?>
<data xmlns="https://www.commcarehq.org/test/TestFormJsonCsvPayloadGenerator/">
    <foo/>
    <bar/>
    <meta>
        <deviceID>TestFormJsonCsvPayloadGenerator</deviceID>
        <timeStart>2011-10-01T15:25:18.404-04</timeStart>
        <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
        <username>admin</username>
        <userID>testy.mctestface</userID>
        <instanceID>{instance_id}</instanceID>
    </meta>
</data>
"""
    submit_form_locally(xform, DOMAIN, **kwargs)
