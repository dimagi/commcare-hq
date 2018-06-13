from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from datetime import datetime

from django.test import TestCase
from sqlalchemy import Date, Integer, SmallInteger, UnicodeText

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.aggregate_ucrs.importer import import_aggregation_models_from_spec
from corehq.apps.aggregate_ucrs.ingestion import populate_aggregate_table_data, get_aggregation_start_period, \
    get_aggregation_end_period
from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
from corehq.apps.aggregate_ucrs.sql.adapter import AggregateIndicatorSqlAdapter
from corehq.apps.aggregate_ucrs.tests.base import AggregationBaseTestMixin
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.userreports.app_manager.helpers import get_form_data_source, get_case_data_source
from corehq.apps.userreports.tasks import _iteratively_build_table
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.utils.xform import FormSubmissionBuilder, TestFormMetadata


class UCRAggregationTest(TestCase, AggregationBaseTestMixin):
    domain = 'agg'
    case_type = 'agg-cases'
    case_name = 'Mary Mom'
    case_date_opened = datetime(2017, 12, 19)
    case_properties = (
        ('first_name', 'First Name', 'string', 'Rowena'),
        ('last_name', 'Last Name', 'string', 'Luk'),
        ('children', 'Children', 'int', '1'),
        ('lmp', 'Pregnancy Start Date', 'date', '2018-01-21'),
        ('delivery_date', 'Pregnancy End Date', 'date', '2018-10-27'),
    )
    fu_visit_dates = (
        datetime(2018, 3, 16),
        datetime(2018, 4, 11),
        datetime(2018, 4, 16),
    )

    @classmethod
    def setUpClass(cls):
        super(UCRAggregationTest, cls).setUpClass()
        # cleanup any previous data
        delete_all_cases()
        delete_all_xforms()
        delete_all_apps()

        # setup app
        factory = AppFactory(domain=cls.domain)
        m0, f0 = factory.new_basic_module('A Module', cls.case_type)
        cls.reg_form = f0
        f0.source = cls._get_xform()
        factory.form_opens_case(f0, case_type=cls.case_type)

        f1 = factory.new_form(m0)
        f1.source = cls._get_xform()
        factory.form_requires_case(f1, case_type=cls.case_type, update={
            cp[0]: '/data/{}'.format(cp[0]) for cp in cls.case_properties
        })
        cls.followup_form = f1
        cls.app = factory.app
        cls.app.save()

        # create form and case ucrs
        cls.form_data_source = get_form_data_source(cls.app, cls.followup_form)
        cls.case_data_source = get_case_data_source(cls.app, cls.case_type)
        # create some data - first just create the case
        cls.case_id = cls._create_case()
        for fu_date in cls.fu_visit_dates:
            cls._submit_followup_form(cls.case_id, received_on=fu_date)

        # populate the UCRs with the data we just created
        cls.case_adapter = get_indicator_adapter(cls.case_data_source)
        cls.form_adapter = get_indicator_adapter(cls.form_data_source)

        cls.case_adapter.rebuild_table()
        cls.form_adapter.rebuild_table()

        _iteratively_build_table(cls.case_data_source)
        _iteratively_build_table(cls.form_data_source)

        # setup/cleanup AggregateTableDefinition
        AggregateTableDefinition.objects.all().delete()
        cls.monthly_aggregate_table_definition = cls._get_monthly_aggregate_table_definition()
        cls.basic_aggregate_table_definition = cls._get_basic_aggregate_table_definition()

    def setUp(self):
        # confirm that our setupClass function properly did its job
        self.assertEqual(1, self.case_adapter.get_query_object().count())
        self.assertEqual(3, self.form_adapter.get_query_object().count())

    @classmethod
    def _get_xform(cls):
        xform = XFormBuilder()
        for prop_name, prop_text, datatype, _ in cls.case_properties:
            xform.new_question(prop_name, prop_text, data_type=datatype)
        return xform.tostring()

    @classmethod
    def _get_case_property_values(cls):
        return {
            cp[0]: cp[-1] for cp in cls.case_properties
        }

    @classmethod
    def _create_case(cls):
        form_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        properties = cls._get_case_property_values()
        caseblock = CaseBlock(
            case_id=case_id,
            case_type=cls.case_type,
            date_opened=cls.case_date_opened,
            case_name=cls.case_name,
            update=properties,
        )
        form_builder = FormSubmissionBuilder(
            form_id=form_id,
            case_blocks=[caseblock],
            form_properties=properties,
        )
        submit_form_locally(form_builder.as_xml_string(), cls.domain)
        return case_id

    @classmethod
    def _submit_followup_form(cls, case_id, received_on):
        form_id = uuid.uuid4().hex
        form_meta = TestFormMetadata(
            domain=cls.domain,
            xmlns=cls.followup_form.xmlns,
            app_id=cls.app._id,
            received_on=received_on,
        )
        properties = cls._get_case_property_values()
        caseblock = CaseBlock(
            case_id=case_id,
            update=properties,
        )
        form_builder = FormSubmissionBuilder(
            form_id=form_id,
            metadata=form_meta,
            case_blocks=[caseblock],
            form_properties=properties,
        )
        submit_form_locally(form_builder.as_xml_string(), cls.domain, received_on=received_on)
        return form_id

    @classmethod
    def _get_monthly_aggregate_table_definition(cls):
        spec = cls.get_monthly_config_spec()
        spec.primary_table.data_source_id = cls.case_data_source._id
        spec.secondary_tables[0].data_source_id = cls.form_data_source._id
        return import_aggregation_models_from_spec(spec)

    @classmethod
    def _get_basic_aggregate_table_definition(cls):
        spec = cls.get_basic_config_spec()
        spec.primary_table.data_source_id = cls.case_data_source._id
        spec.secondary_tables[0].data_source_id = cls.form_data_source._id
        return import_aggregation_models_from_spec(spec)

    def test_aggregate_table(self):
        adapter = AggregateIndicatorSqlAdapter(self.monthly_aggregate_table_definition)
        table = adapter.get_table()
        id_column = table.columns['doc_id']

        # basic checks on primary columns
        self.assertEqual(UnicodeText, type(id_column.type))
        self.assertEqual(True, id_column.primary_key)
        self.assertEqual(Date, type(table.columns['month'].type))
        # todo: pregnancy_start_date should eventually be a date, but nothing in the bootstrap
        # code tells the engine that this is the case. eventually this should be done through
        # the data dictionary.
        self.assertEqual(UnicodeText, type(table.columns['pregnancy_start_date'].type))
        self.assertEqual(Integer, type(table.columns['open_in_month'].type))
        self.assertEqual(SmallInteger, type(table.columns['pregnant_in_month'].type))

        # basic check on secondary column
        self.assertEqual(Integer, type(table.columns['fu_forms_in_month'].type))

    def test_get_aggregation_start_period(self):
        self.assertEqual(self.case_date_opened,
                         get_aggregation_start_period(self.monthly_aggregate_table_definition))

    def test_get_aggregation_end_period(self):
        self.assertEqual(datetime.utcnow().date(),
                         get_aggregation_end_period(self.monthly_aggregate_table_definition).date())

    def test_basic_aggregation(self):
        # next generate our table
        aggregate_table_adapter = AggregateIndicatorSqlAdapter(self.basic_aggregate_table_definition)
        aggregate_table_adapter.rebuild_table()

        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_basic_results()

        # confirm it's also idempotent
        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_basic_results()

    def _check_basic_results(self):
        aggregate_table_adapter = AggregateIndicatorSqlAdapter(self.basic_aggregate_table_definition)
        aggregate_table = aggregate_table_adapter.get_table()
        aggregate_query = aggregate_table_adapter.get_query_object()

        doc_id_column = aggregate_table.c['doc_id']

        # before december the case should not exist
        self.assertEqual(1, aggregate_query.filter(
            doc_id_column == self.case_id,
        ).count())

        row = aggregate_query.filter(
            doc_id_column == self.case_id,
        ).one()
        self.assertEqual(self.case_name, row.name)
        self.assertEqual('2018-01-21', row.pregnancy_start_date)
        self.assertEqual(3, row.fu_forms)

    def test_monthly_aggregation(self):
        # generate our table
        aggregate_table_adapter = AggregateIndicatorSqlAdapter(self.monthly_aggregate_table_definition)
        aggregate_table_adapter.rebuild_table()

        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_results()

        # confirm it's also idempotent
        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_results()

    def _check_results(self):
        aggregate_table_adapter = AggregateIndicatorSqlAdapter(self.monthly_aggregate_table_definition)
        aggregate_table = aggregate_table_adapter.get_table()
        aggregate_query = aggregate_table_adapter.get_query_object()

        doc_id_column = aggregate_table.c['doc_id']
        month_column = aggregate_table.c['month']

        # before december the case should not exist
        self.assertEqual(0, aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column <= '2017-11-01'
        ).count())

        # in december the case should exist, but should not be flagged as pregnant
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2017-12-01'
        ).one()
        self.assertEqual(self.case_name, row.name)
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(0, row.pregnant_in_month)
        self.assertEqual(None, row.fu_forms_in_month)

        # in january the case should exist, and be flagged as pregnant
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-01-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(None, row.fu_forms_in_month)

        # in march the case should exist, be flagged as pregnant, and there is a form
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-03-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(1, row.fu_forms_in_month)

        # in april the case should exist, be flagged as pregnant, and there are 2 forms
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-04-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(2, row.fu_forms_in_month)
