import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from couchexport.models import Format
from pillowtop.es_utils import initialize_index_and_mapping

import requests_mock
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    PathNode,
    TableConfiguration,
)
from corehq.apps.export.models.incremental import (
    IncrementalExport,
    IncrementalExportStatus,
    _generate_incremental_export,
    _send_incremental_export,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.export.tests.util import DEFAULT_CASE_TYPE, new_case
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.motech.const import BASIC_AUTH
from corehq.motech.models import ConnectionSettings
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup


class TestIncrementalExport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, CASE_INDEX_INFO)
            initialize_index_and_mapping(cls.es, USER_INDEX_INFO)

        cls.domain = uuid.uuid4().hex
        create_domain(cls.domain)
        cls.now = datetime.utcnow()
        cases = [
            new_case(domain=cls.domain, foo="apple", bar="banana",
                     server_modified_on=cls.now - timedelta(hours=3)),
            new_case(domain=cls.domain, foo="orange", bar="pear",
                     server_modified_on=cls.now - timedelta(hours=2)),
        ]

        for case in cases:
            send_to_elasticsearch('cases', case.to_json())

        cls.es.indices.refresh(CASE_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.export_instance = CaseExportInstance(
            export_format=Format.UNZIPPED_CSV,
            domain=self.domain,
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
        self.export_instance.save()

        self.incremental_export = IncrementalExport.objects.create(
            domain=self.domain,
            name='test_export',
            export_instance_id=self.export_instance.get_id,
            connection_settings=ConnectionSettings.objects.create(
                domain=self.domain, name='test conn', url='http://somewhere', auth_type=BASIC_AUTH,
            )
        )

    def tearDown(self):
        self.incremental_export.delete()
        self.export_instance.delete()
        super().tearDown()

    def _cleanup_case(self, case_id):
        def _clean():
            self.es.delete(CASE_INDEX_INFO.index, CASE_INDEX_INFO.type, case_id)
            self.es.indices.refresh(CASE_INDEX_INFO.index)
        return _clean

    def test_initial(self):
        checkpoint = _generate_incremental_export(self.incremental_export)
        data = checkpoint.get_blob().read().decode('utf-8-sig')
        expected = "Foo column,Bar column\r\napple,banana\r\norange,pear\r\n"
        self.assertEqual(data, expected)
        self.assertEqual(checkpoint.doc_count, 2)
        return checkpoint

    def test_initial_failure(self):
        # calling it twice should result in the same output since the checkpoints were not
        # marked as success
        self.test_initial()
        self.test_initial()

    def test_incremental_success(self):
        checkpoint = self.test_initial()

        checkpoint.status = IncrementalExportStatus.SUCCESS
        checkpoint.save()

        case = new_case(domain=self.domain, foo="peach", bar="plumb", server_modified_on=datetime.utcnow())
        send_to_elasticsearch('cases', case.to_json())
        self.es.indices.refresh(CASE_INDEX_INFO.index)
        self.addCleanup(self._cleanup_case(case.case_id))

        checkpoint = _generate_incremental_export(self.incremental_export, last_doc_date=checkpoint.last_doc_date)
        data = checkpoint.get_blob().read().decode('utf-8-sig')
        expected = "Foo column,Bar column\r\npeach,plumb\r\n"
        self.assertEqual(data, expected)
        self.assertEqual(checkpoint.doc_count, 1)

        checkpoint = _generate_incremental_export(
            self.incremental_export, last_doc_date=self.now - timedelta(hours=2, minutes=1)
        )
        data = checkpoint.get_blob().read().decode("utf-8-sig")
        expected = "Foo column,Bar column\r\norange,pear\r\npeach,plumb\r\n"
        self.assertEqual(data, expected)
        self.assertEqual(checkpoint.doc_count, 2)

        self.assertEqual(self.incremental_export.checkpoints.count(), 3)

    def test_sending_success(self):
        self._test_sending(200, IncrementalExportStatus.SUCCESS)

    def test_sending_fail(self):
        self._test_sending(401, IncrementalExportStatus.FAILURE)

    def _test_sending(self, status_code, expected_status):
        checkpoint = self.test_initial()
        with requests_mock.Mocker() as m:
            m.post('http://somewhere/', status_code=status_code)
            _send_incremental_export(self.incremental_export, checkpoint)

            checkpoint.refresh_from_db()
            self.assertEqual(checkpoint.status, expected_status)
            self.assertEqual(checkpoint.request_log.response_status, status_code)

    def test_owner_filter(self):
        setup_locations_and_types(
            self.domain,
            ['state', 'health-department', 'team', 'sub-team'],
            [],
            [
                ('State1', [
                    ('HealthDepartment1', [
                        ('Team1', [
                            ('SubTeam1', []),
                            ('SubTeam2', []),
                        ]),
                        ('Team2', []),
                    ]),
                ])
            ]
        )
        team1 = SQLLocation.objects.filter(domain=self.domain, name='Team1').first()
        health_department = SQLLocation.objects.filter(domain=self.domain, name='HealthDepartment1').first()
        self.addCleanup(delete_all_locations)

        user = CommCareUser.create(self.domain, 'm2', 'abc', location=team1)
        send_to_elasticsearch('users', user.to_json())
        self.es.indices.refresh(USER_INDEX_INFO.index)
        self.addCleanup(delete_all_users)

        cases = [
            new_case(
                domain=self.domain,
                foo="peach",
                bar="plumb",
                server_modified_on=datetime.utcnow() + timedelta(hours=-1),
                owner_id='123',
            ),
            new_case(
                domain=self.domain,
                foo="orange",
                bar="melon",
                server_modified_on=datetime.utcnow(),
                owner_id=user.user_id,  # this user is part of the team1 location.
            ),
            new_case(
                domain=self.domain,
                foo="grape",
                bar="pineapple",
                server_modified_on=datetime.utcnow(),
            ),
        ]
        for case in cases:
            send_to_elasticsearch("cases", case.to_json())
            self.addCleanup(self._cleanup_case(case.case_id))

        self.es.indices.refresh(CASE_INDEX_INFO.index)

        self.export_instance.filters.show_project_data = False
        self.export_instance.filters.locations = [health_department.location_id]
        self.export_instance.filters.users = ['123']
        self.export_instance.save()

        checkpoint = _generate_incremental_export(self.incremental_export)

        data = checkpoint.get_blob().read().decode("utf-8-sig")
        expected = "Foo column,Bar column\r\npeach,plumb\r\norange,melon\r\n"
        self.assertEqual(data, expected)
