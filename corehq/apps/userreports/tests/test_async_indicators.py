import uuid

from django.test import SimpleTestCase, TestCase

import mock

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.models import (
    AsyncIndicator,
    DataSourceConfiguration,
)
from corehq.apps.userreports.tasks import build_async_indicators
from corehq.apps.userreports.tests.utils import load_data_from_db
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name


class RunAsynchronousTest(SimpleTestCase):
    def _create_data_source_config(self, indicators=None):
        default_indicator = [{
            "type": "expression",
            "column_id": "laugh_sound",
            "datatype": "string",
            "expression": {
                'type': 'named',
                'name': 'laugh_sound'
            }
        }]

        return DataSourceConfiguration.wrap({
            'display_name': 'Mother Indicators',
            'doc_type': 'DataSourceConfiguration',
            'domain': 'test',
            'referenced_doc_type': 'CommCareCase',
            'table_id': 'mother_indicators',
            'configured_filter': {},
            'configured_indicators': indicators or default_indicator
        })

    def test_async_not_configured(self):
        indicator_configuration = self._create_data_source_config()
        adapter = get_indicator_adapter(indicator_configuration)
        self.assertFalse(adapter.run_asynchronous)

    def test_async_configured(self):
        indicator_configuration = self._create_data_source_config()
        indicator_configuration.asynchronous = True
        adapter = get_indicator_adapter(indicator_configuration)
        self.assertTrue(adapter.run_asynchronous)

    # def test_related_doc_expression(self):
    #     indicator_configuration = self._create_data_source_config([{
    #         "datatype": "string",
    #         "type": "expression",
    #         "column_id": "confirmed_referral_target",
    #         "expression": {
    #             "type": "related_doc",
    #             "related_doc_type": "CommCareUser",
    #             "doc_id_expression": {
    #                 "type": "property_path",
    #                 "property_path": ["form", "meta", "userID"]
    #             },
    #             "value_expression": {
    #                 "type": "property_path",
    #                 "property_path": [
    #                     "user_data",
    #                     "confirmed_referral_target"
    #                 ]
    #             }
    #         }
    #     }])
    #
    #     adapter = get_indicator_adapter(indicator_configuration)
    #     self.assertTrue(adapter.run_asynchronous)
    #
    # def test_named_expression(self):
    #     indicator_configuration = get_data_source_with_related_doc_type()
    #     adapter = get_indicator_adapter(indicator_configuration)
    #     self.assertTrue(adapter.run_asynchronous)


class TestBulkUpdate(TestCase):
    def tearDown(self):
        AsyncIndicator.objects.all().delete()

    def _get_indicator_data(self):
        return {
            i.doc_id: i.indicator_config_ids
            for i in AsyncIndicator.objects.all()
        }

    def test_update_record(self):
        domain = 'test-update-record'
        doc_type = 'form'
        initial_data = {
            'd1': ['c1', 'c2'],
            'd2': ['c1'],
            'd3': ['c2']
        }
        AsyncIndicator.objects.bulk_create([
            AsyncIndicator(
                doc_id=doc_id, doc_type=doc_type, domain=domain, indicator_config_ids=sorted(config_ids))
            for doc_id, config_ids in initial_data.items()
        ])
        updated_data = {
            'd2': ['c2'],
            'd3': ['c3'],
            'd4': ['c2', 'c1'],
            'd5': ['c4']
        }

        with self.assertNumQueries(3):
            # 3 queries, 1 for query, 1 for update, 1 for create
            doc_type_by_ids = {i: doc_type for i in ['d1', 'd2', 'd3', 'd4', 'd5']}
            AsyncIndicator.bulk_update_records(updated_data, domain, doc_type_by_ids)

        self.assertEqual(
            self._get_indicator_data(),
            {
                'd1': ['c1', 'c2'],
                'd2': ['c1', 'c2'],
                'd3': ['c2', 'c3'],
                'd4': ['c1', 'c2'],
                'd5': ['c4']
            }
        )


class BulkAsyncIndicatorProcessingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BulkAsyncIndicatorProcessingTest, cls).setUpClass()
        domain_name = "bulk_async_indicator_processing"
        cls.domain = Domain.get_or_create_with_name(domain_name, is_active=True)

        def _make_config(indicators):
            return DataSourceConfiguration(
                domain=domain_name,
                display_name='foo',
                referenced_doc_type='CommCareCase',
                table_id=clean_table_name(domain_name, str(uuid.uuid4().hex)),
                configured_indicators=indicators
            )

        cls.config1 = _make_config(
            [{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'name'
                },
                "column_id": 'name',
                "display_name": 'name',
                "datatype": "string"
            }]
        )
        cls.config1.save()
        cls.config2 = _make_config(
            [{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'color'
                },
                "column_id": 'color',
                "display_name": 'color',
                "datatype": "string"
            }]
        )
        cls.config2.save()

        cls.adapters = []
        for config in [cls.config1, cls.config2]:
            adapter = get_indicator_adapter(config, raise_errors=True)
            adapter.build_table()
            cls.adapters.append(adapter)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(BulkAsyncIndicatorProcessingTest, cls).tearDownClass()

    def _setup_docs_and_indicators(self):
        self.docs = [
            {
                "_id": str(i),
                "domain": self.domain.name,
                "doc_type": "CommCareCase",
                "name": 'doc_name_' + str(i),
                "color": 'doc_color_' + str(i)
            }
            for i in range(10)
        ]
        self.doc_ids = [str(i) for i in range(10)]

        AsyncIndicator.bulk_creation(
            [doc["_id"] for doc in self.docs],
            "CommCareCase",
            self.domain,
            []
        )

    def setUp(self):
        self._setup_docs_and_indicators()

        def fake_iter_documents(_, ids):
            return [doc for doc in self.docs if doc['_id'] in ids]

        # patch this to allow counting success/failure counts
        _patch = mock.patch('corehq.apps.userreports.tasks.datadog_counter')
        self.datadog_patch = _patch.start()
        # patch docstore to avoid overhead of saving/querying docs
        docstore_patch = mock.patch(
            'corehq.form_processor.document_stores.CaseDocumentStore.iter_documents',
            new=fake_iter_documents
        )
        docstore_patch.start()
        self.addCleanup(_patch.stop)
        self.addCleanup(docstore_patch.stop)

    def tearDown(self):
        AsyncIndicator.objects.all().delete()
        for adapter in self.adapters:
            adapter.clear_table()

    def indicators(self):
        return AsyncIndicator.objects.all()

    def _assert_rows_in_ucr_table(self, config, rows):
        results = list(load_data_from_db(get_table_name(self.domain.name, config.table_id)))
        if not rows:
            self.assertEqual(results, [])
            return
        actual_rows = [{key: r[key] for key in rows[0]} for r in results]

        self.assertEqual(
            sorted(rows, key=lambda x: x['doc_id']),
            sorted(actual_rows, key=lambda x: x['doc_id'])
        )

    def test_basic_run(self):
        # map some indicators to first config, other to the second config
        #   make sure that the tables get correctly built
        AsyncIndicator.objects.filter(
            doc_id__in=self.doc_ids[0:5]
        ).update(indicator_config_ids=[self.config1._id])
        AsyncIndicator.objects.filter(
            doc_id__in=self.doc_ids[5:]
        ).update(indicator_config_ids=[self.config2._id])

        build_async_indicators(self.doc_ids)

        self._assert_rows_in_ucr_table(self.config1, [
            {'doc_id': d["_id"], 'name': d["name"]} for d in self.docs[0:5]
        ])
        self._assert_rows_in_ucr_table(self.config2, [
            {'doc_id': d["_id"], 'color': d["color"]} for d in self.docs[5:]
        ])
        self.datadog_patch.assert_has_calls([
            mock.call('commcare.async_indicator.processed_success', 10),
            mock.call('commcare.async_indicator.processed_fail', 0)
        ])

    def test_known_exception(self):
        # check that exceptions due to unknown configs are handled correctly
        AsyncIndicator.objects.filter(
            doc_id__in=self.doc_ids
        ).update(indicator_config_ids=["unknown"])
        build_async_indicators(self.doc_ids)

        # since the only config associated with indicators is
        #   unknown, all the indicators should be deleted
        self.assertEqual(AsyncIndicator.objects.count(), 0)
        self.datadog_patch.assert_has_calls([
            mock.call('commcare.async_indicator.processed_success', 10),
            mock.call('commcare.async_indicator.processed_fail', 0)
        ])

    def test_unknown_exception(self):
        # check that an unknown exception in bulk_save gets handled correctly
        AsyncIndicator.objects.filter(
            doc_id__in=self.doc_ids
        ).update(indicator_config_ids=[self.config1._id, "unknown_id"])
        with mock.patch("corehq.apps.userreports.tasks.get_indicator_adapter") as adapter_mock:
            adapter_mock.side_effect = Exception("Some random exception")
            build_async_indicators(self.doc_ids)

        # no indicator should be deleted since there was no success
        self.assertEqual(AsyncIndicator.objects.count(), 10)
        # the non-existent 'unknown_id' should be removed from indicator_config_ids
        #   but self.config1._id should still be present
        self.assertEqual(
            AsyncIndicator.objects.filter(indicator_config_ids=[self.config1._id]).count(),
            10
        )
        self.datadog_patch.assert_has_calls([
            mock.call('commcare.async_indicator.processed_success', 0),
            mock.call('commcare.async_indicator.processed_fail', 10)
        ])
