from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.query import QuerySet
from django.http import QueryDict
from django.test import TestCase
from django.test.utils import override_settings

import django_tables2 as tables

from couchexport.models import Format

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseSearchES, case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqwebapp.tables.elasticsearch.records import (
    CaseSearchElasticRecord,
)
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.export import (
    TableExportException,
    TableExportMixin,
)
from corehq.apps.hqwebapp.tasks import export_all_rows_task
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import create_case


class DummyTable(tables.Table):
    col1 = tables.Column()
    col2 = tables.Column()


class BaseTestView(TableExportMixin):
    table_class = DummyTable
    export_format = Format.XLS_2007
    exclude_columns_in_export = ()

    def __init__(self, **kwargs):
        self.request = MagicMock()
        self.request.GET = QueryDict()
        self.request.domain = "test-domain"
        self.request.can_access_all_locations = True
        self.request.couch_user = MagicMock(user_id="user-id")


class TableDataView(BaseTestView):
    table_class = DummyTable
    table_data = [
        {"col1": "a", "col2": "b"},
        {"col1": "c", "col2": "d"},
    ]


class ObjectListView(BaseTestView):

    @property
    def object_list(self):
        for data in [
            SimpleNamespace(col1="a", col2="b"),
            SimpleNamespace(col1="c", col2="d"),
        ]:
            yield data


class DummyModel(models.Model):
    col1 = models.CharField(max_length=10)
    col2 = models.CharField(max_length=10)

    class Meta:
        app_label = 'testapp'


class QuerysetView(BaseTestView):

    def get_queryset(self):
        objs = [
            DummyModel(col1="a", col2="b"),
            DummyModel(col1="c", col2="d"),
        ]
        return self.fake_queryset(objs)

    @staticmethod
    def fake_queryset(objs):
        qs = MagicMock(spec=QuerySet)
        qs.__iter__.return_value = iter(objs)
        qs.model = DummyModel
        return qs


class DummyElasticTable(DummyTable, ElasticTable):
    record_class = CaseSearchElasticRecord


class ElasticTableView(BaseTestView):
    table_class = DummyElasticTable

    def get_queryset(self):
        return CaseSearchES().case_type('foobar').domain('test-domain')


@es_test(requires=[case_search_adapter], setup_class=True)
class BaseCaseSearchTestSetup(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_type = 'foobar'
        cls.domain_obj = create_domain(cls.domain)
        cls.web_user = WebUser.create(cls.domain, 'test-user', 'password', None, None, is_admin=True)
        cls.web_user.save()

        cls.case_a = create_case(
            cls.domain,
            case_type=case_type,
            name='CaseA',
            case_json={
                'col1': 'a',
                'col2': 'b',
            },
            save=True
        )
        cls.case_b = create_case(
            cls.domain,
            case_type=case_type,
            name='CaseB',
            case_json={
                'col1': 'c',
                'col2': 'd',
            },
            save=True,
        )
        case_search_adapter.bulk_index([cls.case_a, cls.case_b], refresh=True)

    @classmethod
    def tearDownClass(cls):
        for case in [cls.case_a, cls.case_b]:
            case.delete()
        cls.web_user.delete(None, None)
        super().tearDownClass()


class TestTableExportMixinExportData(BaseCaseSearchTestSetup):

    def _assert_for_sheet_and_rows(self, view, sheet_name, rows_list):
        self.assertEqual(sheet_name, view.get_export_sheet_name())
        # Headers are capitalized in the export
        self.assertEqual(rows_list[0], ['Col1', 'Col2'])
        self.assertEqual(rows_list[1], ['a', 'b'])
        self.assertEqual(rows_list[2], ['c', 'd'])

    def test_with_table_data_attribute(self):
        view = TableDataView()
        sheet_name, rows = view._export_table_data[0]
        self._assert_for_sheet_and_rows(view, sheet_name, list(rows))

    def test_with_object_list_attribute(self):
        view = ObjectListView()
        sheet_name, rows = view._export_table_data[0]
        self._assert_for_sheet_and_rows(view, sheet_name, list(rows))

    def test_with_get_queryset_method(self):
        view = QuerysetView()
        sheet_name, rows = view._export_table_data[0]
        self._assert_for_sheet_and_rows(view, sheet_name, list(rows))

    def test_with_exclude_columns(self):
        view = TableDataView()
        view.exclude_columns_in_export = ('col1',)
        sheet_name, rows = view._export_table_data[0]
        rows_list = list(rows)
        self.assertEqual(rows_list[0], ['Col2'])
        self.assertEqual(rows_list[1], ['b'])
        self.assertEqual(rows_list[2], ['d'])

    def test_with_elastic_table(self):
        view = ElasticTableView()
        view.request.couch_user = self.web_user
        sheet_name, rows = view._export_table_data[0]
        self._assert_for_sheet_and_rows(view, sheet_name, list(rows))


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestTableExportMixinTriggerExport(TestCase):

    @patch('corehq.apps.hqwebapp.tables.export.export_all_rows_task.delay')
    def test_trigger_export_with_table_data(self, *args):
        view = TableDataView()
        response = view.trigger_export(recipient_list=None, subject=None)
        self.assertEqual(
            str(response.content, encoding='utf-8'),
            "Export is being generated. You will receive an email when it is ready."
        )

    @patch('corehq.apps.hqwebapp.tables.export.export_all_rows_task.delay')
    def test_trigger_export_with_object_list(self, *args):
        view = ObjectListView()
        response = view.trigger_export(recipient_list=None, subject=None)
        self.assertEqual(
            str(response.content, encoding='utf-8'),
            "Export is being generated. You will receive an email when it is ready."
        )

    @patch('corehq.apps.hqwebapp.tables.export.export_all_rows_task.delay')
    def test_trigger_export_with_get_queryset(self, *args):
        view = QuerysetView()
        response = view.trigger_export(recipient_list=None, subject=None)
        self.assertEqual(
            str(response.content, encoding='utf-8'),
            "Export is being generated. You will receive an email when it is ready."
        )

    def test_trigger_export_without_table_class(self):
        view = BaseTestView()
        view.table_class = None
        with self.assertRaises(ImproperlyConfigured) as err:
            view.trigger_export()
        self.assertEqual(
            str(err.exception),
            "TableExportMixin requires `self.table_class`."
        )

    def test_trigger_export_without_request(self):
        view = BaseTestView()
        view.request = None
        with self.assertRaises(ImproperlyConfigured) as err:
            view.trigger_export()
        self.assertEqual(
            str(err.exception),
            "TableExportMixin requires `self.request`."
        )

    @patch('corehq.apps.hqwebapp.tables.export.export_all_rows_task', wraps=export_all_rows_task)
    def test_trigger_export_with_invalid_export_format(self, *args):
        view = TableDataView()
        view.export_format = "INVALID_FORMAT"
        with self.assertRaises(TableExportException) as err:
            view.trigger_export()
        self.assertEqual(
            str(err.exception),
            "Unsupported export format: {}. Supported formats are: {}".format(
                view.export_format,
                ','.join(view._SUPPORTED_FORMATS)
            )
        )
