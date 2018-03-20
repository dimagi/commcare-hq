from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import json
import uuid
from django.test.testcases import SimpleTestCase
from mock import patch

from couchexport.models import Format

from corehq.apps.export.export import get_export_file
from corehq.apps.export.models import SMSExportInstance, SMSExportDataSchema
from corehq.apps.sms.models import WORKFLOWS_FOR_REPORTS


class TestSmsExport(SimpleTestCase):
    domain = uuid.uuid4().hex
    maxDiff = None

    def _make_message(self, id, couch_recipient_doc_type='CommCareUser', workflow='BROADCAST'):
        return {
            '_id': id,
            'domain': self.domain,
            'phone_number': '+15555555',
            'text': 'message',
            'couch_recipient_doc_type': couch_recipient_doc_type,
            'couch_recipient': '1234',
            'direction': 'O',
            'workflow': workflow,
            'date': datetime.datetime(2017, 1, 1)
        }

    def _message_docs(self):
        return [
            self._make_message(uuid.uuid4().hex, workflow=workflow)
            for workflow in WORKFLOWS_FOR_REPORTS
        ]

    def _make_message_rows(self, docs, include_meta=False):
        rows = []
        for doc in docs:
            row = [
                'Mobile Worker',
                doc['couch_recipient'],
                doc['date'].strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                '---',
                doc['phone_number'],
                doc['direction'],
                doc['text'],
                doc['workflow'].lower()
            ]
            if include_meta:
                row.append(doc['_id'])
            rows.append(row)
        return rows

    @classmethod
    def setUpClass(cls):
        super(TestSmsExport, cls).setUpClass()
        cls.schema_meta = SMSExportDataSchema.get_latest_export_schema(
            domain=cls.domain, include_metadata=True
        )
        cls.schema_no_meta = SMSExportDataSchema.get_latest_export_schema(
            domain=cls.domain, include_metadata=False
        )
        cls.export_meta = SMSExportInstance._new_from_schema(cls.schema_meta)
        cls.export_no_meta = SMSExportInstance._new_from_schema(cls.schema_no_meta)
        cls.export_meta.export_format = Format.JSON
        cls.export_no_meta.export_format = Format.JSON

    @patch('corehq.apps.export.transforms.cached_user_id_to_username')
    @patch('corehq.apps.export.export.get_export_documents')
    def test_export(self, docs, owner_id_to_display):
        docs.return_value = self._message_docs()
        owner_id_to_display.return_value = None

        export_file = get_export_file([self.export_no_meta], [])

        with export_file as export:
            self.assertEqual(
                json.loads(export.read()),
                {
                    'Messages': {
                        'headers': [
                            'Contact Type',
                            'Contact ID',
                            'Timestamp',
                            'User Name',
                            'Phone Number',
                            'Direction',
                            'Message',
                            'Type',
                        ],
                        'rows': self._make_message_rows(docs()),
                    }
                }
            )

    @patch('corehq.apps.export.transforms.cached_user_id_to_username')
    @patch('corehq.apps.export.export.get_export_documents')
    def test_export_meta(self, docs, owner_id_to_display):
        docs.return_value = self._message_docs()
        owner_id_to_display.return_value = None

        export_file = get_export_file([self.export_meta], [])

        with export_file as export:
            self.assertEqual(
                json.loads(export.read()),
                {
                    'Messages': {
                        'headers': [
                            'Contact Type',
                            'Contact ID',
                            'Timestamp',
                            'User Name',
                            'Phone Number',
                            'Direction',
                            'Message',
                            'Type',
                            'Message Log ID',
                        ],
                        'rows': self._make_message_rows(docs(), include_meta=True),
                    }
                }
            )

    @patch('corehq.apps.export.transforms._cached_case_id_to_case_name')
    @patch('corehq.apps.export.transforms.cached_user_id_to_username')
    @patch('corehq.apps.export.export.get_export_documents')
    def test_export_doc_type_transform(self, docs, owner_id_to_display, case_id_to_casename):
        docs.return_value = [
            self._make_message(1234, couch_recipient_doc_type='WebUser'),
            self._make_message(1235, couch_recipient_doc_type='CommCareCase'),
            self._make_message(1236, couch_recipient_doc_type='Location'),
        ]
        owner_id_to_display.return_value = None
        case_id_to_casename.return_value = None
        rows_value = self._make_message_rows(docs())
        rows_value[0][0] = 'Web User'
        rows_value[1][0] = 'Case'
        rows_value[2][0] = 'Unknown'

        export_file = get_export_file([self.export_no_meta], [])

        with export_file as export:
            self.assertEqual(
                json.loads(export.read()),
                {
                    'Messages': {
                        'headers': [
                            'Contact Type',
                            'Contact ID',
                            'Timestamp',
                            'User Name',
                            'Phone Number',
                            'Direction',
                            'Message',
                            'Type',
                        ],
                        'rows': rows_value
                    }
                }
            )

    @patch('corehq.apps.export.transforms.cached_user_id_to_username')
    @patch('corehq.apps.export.export.get_export_documents')
    def test_export_workflow_transform(self, docs, owner_id_to_display):
        messages = [
            self._make_message(1234, workflow='blah'),
            self._make_message(1235, workflow=''),
        ]
        messages[1]['xforms_session_couch_id'] = 'test'
        docs.return_value = messages
        owner_id_to_display.return_value = None
        rows_value = self._make_message_rows(docs())
        rows_value[0][-1] = 'other'
        rows_value[1][-1] = 'survey'

        export_file = get_export_file([self.export_no_meta], [])

        with export_file as export:
            self.assertEqual(
                json.loads(export.read()),
                {
                    'Messages': {
                        'headers': [
                            'Contact Type',
                            'Contact ID',
                            'Timestamp',
                            'User Name',
                            'Phone Number',
                            'Direction',
                            'Message',
                            'Type',
                        ],
                        'rows': rows_value,
                    }
                }
            )

    @patch('corehq.apps.export.transforms._cached_case_id_to_case_name')
    @patch('corehq.apps.export.transforms.cached_user_id_to_username')
    @patch('corehq.apps.export.export.get_export_documents')
    def test_export_recipient_id_transform(self, docs, owner_id_to_display, case_id_to_casename):
        docs.return_value = [
            self._make_message(1234, couch_recipient_doc_type='WebUser'),
            self._make_message(1235, couch_recipient_doc_type='CommCareCase'),
            self._make_message(1236, couch_recipient_doc_type='Location'),
        ]
        owner_id_to_display.return_value = 'web user'
        case_id_to_casename.return_value = 'case'
        rows_value = self._make_message_rows(docs())
        rows_value[0][0] = 'Web User'
        rows_value[0][3] = 'web user'
        rows_value[1][0] = 'Case'
        rows_value[1][3] = 'case'
        rows_value[2][0] = 'Unknown'

        export_file = get_export_file([self.export_no_meta], [])

        with export_file as export:
            self.assertEqual(
                json.loads(export.read()),
                {
                    'Messages': {
                        'headers': [
                            'Contact Type',
                            'Contact ID',
                            'Timestamp',
                            'User Name',
                            'Phone Number',
                            'Direction',
                            'Message',
                            'Type',
                        ],
                        'rows': rows_value
                    }
                }
            )
