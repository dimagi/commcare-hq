import inspect
import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.export.export import get_export_file
from corehq.apps.export.models import CaseExportInstance, TableConfiguration, ExportColumn, ExportItem, PathNode
from corehq.apps.export.models.incremental import IncrementalExport
from corehq.apps.export.tasks import _generate_incremental_export
from corehq.apps.export.tests.util import new_case, DEFAULT_CASE_TYPE, get_export_json
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.motech.const import BASIC_AUTH
from corehq.motech.models import ConnectionSettings
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from couchexport.models import Format
from pillowtop.es_utils import initialize_index_and_mapping


class TestIncrementalExport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, CASE_INDEX_INFO)

        cls.domain = uuid.uuid4().hex
        now = datetime.utcnow()
        cases = [
            new_case(domain=cls.domain, foo="apple", bar="banana", server_modified_on=now - timedelta(hours=3)),
            new_case(domain=cls.domain, foo="orange", bar="pear", server_modified_on=now - timedelta(hours=2)),
        ]

        for case in cases:
            send_to_elasticsearch('cases', case.to_json())

        cls.es.indices.refresh(CASE_INDEX_INFO.index)

        cls.export_instance = CaseExportInstance(
            export_format=Format.UNZIPPED_CSV,
            domain=cls.domain,
            case_type=DEFAULT_CASE_TYPE,
            tables=[TableConfiguration(
                label="My table",
                selected=True,
                path=[],
                columns=[
                    ExportColumn(
                        label="Foo column",
                        item=ExportItem(
                            path=[PathNode(name="foo")]
                        ),
                        selected=True,
                    ),
                    ExportColumn(
                        label="Bar column",
                        item=ExportItem(
                            path=[PathNode(name="bar")]
                        ),
                        selected=True,
                    )
                ]
            )]
        )
        cls.export_instance.save()

        cls.incremental_export = IncrementalExport.objects.create(
            domain=cls.domain,
            name='test_export',
            export_instance_id=cls.export_instance.get_id,
            connection_settings=ConnectionSettings.objects.create(
                domain=cls.domain, name='test conn', url='somewhere', auth_type=BASIC_AUTH,
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.incremental_export.delete()
        cls.export_instance.delete()
        ensure_index_deleted(CASE_INDEX_INFO.index)
        super().tearDownClass()

    def test_incremental(self):
        checkpoint = _generate_incremental_export(self.incremental_export)
        self.assertTrue(checkpoint.blob_exists)
        data = checkpoint.get_blob().read().decode('utf-8-sig')
        expected = "Foo column,Bar column\r\napple,banana\r\norange,pear\r\n"
        self.assertEqual(data, expected)

        case = new_case(domain=self.domain, foo="peach", bar="plumb", server_modified_on=datetime.utcnow())
        send_to_elasticsearch('cases', case.to_json())
        self.es.indices.refresh(CASE_INDEX_INFO.index)

        checkpoint = _generate_incremental_export(self.incremental_export)
        data = checkpoint.get_blob().read().decode('utf-8-sig')
        expected = "Foo column,Bar column\r\npeach,plumb\r\n"
        self.assertEqual(data, expected)
