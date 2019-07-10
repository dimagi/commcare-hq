from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from datetime import datetime

from django.test import TestCase
from sqlalchemy import Date, Integer, SmallInteger, UnicodeText

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import post_case_blocks
from corehq.apps.aggregate_ucrs.aggregations import AGGREGATION_UNIT_CHOICE_WEEK
from corehq.apps.aggregate_ucrs.importer import import_aggregation_models_from_spec
from corehq.apps.aggregate_ucrs.ingestion import populate_aggregate_table_data, get_aggregation_start_period, \
    get_aggregation_end_period
from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
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
    case_name = 'Mama'
    case_date_opened = datetime(2017, 12, 19)
    closed_case_date_opened = datetime(2018, 1, 7)
    closed_case_date_closed = datetime(2018, 3, 7)
    case_properties = (
        ('first_name', 'First Name', 'string', 'Mama'),
        ('last_name', 'Last Name', 'string', 'Luck'),
        ('children', 'Children', 'int', '1'),
        ('lmp', 'Pregnancy Start Date', 'date', '2018-01-21'),
        ('delivery_date', 'Pregnancy End Date', 'date', '2018-10-27'),
    )
    fu_visit_dates = (
        datetime(2018, 3, 16),
        datetime(2018, 4, 11),
        datetime(2018, 4, 15),
    )
    parent_case_type = 'parent'
    parent_name = 'Mama'

    @classmethod
    def setUpClass(cls):
        super(UCRAggregationTest, cls).setUpClass()
        # cleanup any previous data
        cls._cleanup_data()

        # setup app
        factory = AppFactory(domain=cls.domain)
        # parent case module, incl opening child cases of main type
        m_parent, f_parent = factory.new_basic_module('Parent Module', cls.parent_case_type)
        factory.form_opens_case(f_parent, case_type=cls.parent_case_type)
        factory.form_opens_case(f_parent, case_type=cls.case_type, is_subcase=True)

        # main module
        m0, f0 = factory.new_basic_module('A Module', cls.case_type)
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
        cls.parent_case_data_source = get_case_data_source(cls.app, cls.parent_case_type)

        # create some data - first just create the case
        cls.parent_case_id = cls._create_parent_case(cls.parent_name)
        cls.case_id = cls._create_case(cls.parent_case_id)
        for fu_date in cls.fu_visit_dates:
            cls._submit_followup_form(cls.case_id, received_on=fu_date)

        # the closed case causes there to be some data with an end_column
        cls.closed_case_id = cls._create_closed_case()

        # populate the UCRs with the data we just created
        cls.form_adapter = get_indicator_adapter(cls.form_data_source)
        cls.case_adapter = get_indicator_adapter(cls.case_data_source)
        cls.parent_case_adapter = get_indicator_adapter(cls.parent_case_data_source)

        cls.form_adapter.rebuild_table()
        cls.case_adapter.rebuild_table()
        cls.parent_case_adapter.rebuild_table()

        _iteratively_build_table(cls.form_data_source)
        _iteratively_build_table(cls.case_data_source)
        _iteratively_build_table(cls.parent_case_data_source)

        # setup AggregateTableDefinition
        cls.monthly_aggregate_table_definition = cls._get_monthly_aggregate_table_definition()
        cls.weekly_aggregate_table_definition = cls._get_weekly_aggregate_table_definition()
        cls.basic_aggregate_table_definition = cls._get_basic_aggregate_table_definition()

        # and adapter
        cls.monthly_adapter = get_indicator_adapter(cls.monthly_aggregate_table_definition)

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_data()
        super(UCRAggregationTest, cls).tearDownClass()

    @classmethod
    def _cleanup_data(cls):
        delete_all_cases()
        delete_all_xforms()
        delete_all_apps()
        AggregateTableDefinition.objects.all().delete()

    def setUp(self):
        # confirm that our setupClass function properly did its job
        self.assertEqual(3, self.form_adapter.get_query_object().count())
        self.assertEqual(2, self.case_adapter.get_query_object().count())
        self.assertEqual(1, self.parent_case_adapter.get_query_object().count())

    @classmethod
    def _get_xform(cls):
        xform = XFormBuilder()
        for prop_name, prop_text, datatype, _ in cls.case_properties:
            xform.new_question(prop_name, prop_text, data_type=datatype)
        return xform.tostring().decode('utf-8')

    @classmethod
    def _get_case_property_values(cls):
        return {
            cp[0]: cp[-1] for cp in cls.case_properties
        }

    @classmethod
    def _create_case(cls, parent_id):
        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            case_id=case_id,
            case_type=cls.case_type,
            date_opened=cls.case_date_opened,
            case_name=cls.case_name,
            update=cls._get_case_property_values(),
            index={
                'parent': (cls.case_type, parent_id)
            }
        )
        post_case_blocks([caseblock.as_xml()], domain=cls.domain)
        return case_id

    @classmethod
    def _create_closed_case(cls):
        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            case_id=case_id,
            case_type=cls.case_type,
            date_opened=cls.closed_case_date_opened,
            date_modified=cls.closed_case_date_closed,
            case_name=cls.case_name,
            close=True,
        )
        post_case_blocks([caseblock.as_xml()], domain=cls.domain)
        return case_id

    @classmethod
    def _create_parent_case(cls, case_name):
        parent_id = uuid.uuid4().hex
        post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=parent_id,
                    case_name=case_name,
                    case_type=cls.parent_case_type,
                ).as_xml()
            ], domain=cls.domain
        )
        return parent_id

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
        submit_form_locally(form_builder.as_xml_string(), cls.domain, received_on=received_on, app_id=cls.app._id)
        return form_id

    @classmethod
    def _get_monthly_aggregate_table_definition(cls):
        spec = cls.get_monthly_config_spec()
        spec.primary_table.data_source_id = cls.case_data_source._id
        spec.secondary_tables[0].data_source_id = cls.form_data_source._id
        return import_aggregation_models_from_spec(spec)

    @classmethod
    def _get_weekly_aggregate_table_definition(cls):
        spec = cls.get_monthly_config_spec()
        spec.table_id = 'weekly_aggregate_pregnancies'
        spec.primary_table.data_source_id = cls.case_data_source._id
        spec.secondary_tables[0].data_source_id = cls.form_data_source._id
        spec.time_aggregation.unit = AGGREGATION_UNIT_CHOICE_WEEK
        return import_aggregation_models_from_spec(spec)

    @classmethod
    def _get_basic_aggregate_table_definition(cls):
        spec = cls.get_basic_config_spec()
        spec.primary_table.data_source_id = cls.case_data_source._id
        spec.secondary_tables[0].data_source_id = cls.form_data_source._id
        spec.secondary_tables[1].data_source_id = cls.parent_case_data_source._id
        return import_aggregation_models_from_spec(spec)

    def test_aggregate_table(self):
        table = self.monthly_adapter.get_table()
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
        self.assertEqual(SmallInteger, type(table.columns['fu_forms_in_month'].type))

    def test_get_aggregation_start_period(self):
        self.assertEqual(self.case_date_opened,
                         get_aggregation_start_period(self.monthly_aggregate_table_definition))

    def test_get_aggregation_end_period(self):
        self.assertEqual(datetime.utcnow().date(),
                         get_aggregation_end_period(self.monthly_aggregate_table_definition).date())

    def test_basic_aggregation(self):
        # next generate our table
        aggregate_table_adapter = get_indicator_adapter(self.basic_aggregate_table_definition)
        aggregate_table_adapter.rebuild_table()

        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_basic_results()

        # confirm it's also idempotent
        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_basic_results()

    def _check_basic_results(self):
        aggregate_table_adapter = get_indicator_adapter(self.basic_aggregate_table_definition)
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
        aggregate_table_adapter = self.monthly_adapter
        aggregate_table_adapter.rebuild_table()

        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_monthly_results()

        # confirm it's also idempotent
        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_monthly_results()

    def _check_monthly_results(self):
        aggregate_table_adapter = self.monthly_adapter
        aggregate_table = aggregate_table_adapter.get_table()
        aggregate_query = aggregate_table_adapter.get_query_object()

        doc_id_column = aggregate_table.c['doc_id']
        month_column = aggregate_table.c['month']

        # before december no case should not exist
        self.assertEqual(0, aggregate_query.filter(
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
        self.assertEqual(None, row.any_fu_forms_in_month)
        # and the closed case should still not exist
        self.assertEqual(0, aggregate_query.filter(
            doc_id_column == self.closed_case_id,
            month_column == '2017-12-01',
        ).count())

        # in january the case should exist, and be flagged as pregnant
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-01-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(None, row.fu_forms_in_month)
        self.assertEqual(None, row.any_fu_forms_in_month)
        # and the closed case is now live
        self.assertEqual(1, aggregate_query.filter(
            doc_id_column == self.closed_case_id,
            month_column == '2018-01-01',
        ).count())

        # in march the case should exist, be flagged as pregnant, and there is a form
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-03-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(1, row.fu_forms_in_month)
        self.assertEqual(1, row.any_fu_forms_in_month)
        # the closed case is still live
        self.assertEqual(1, aggregate_query.filter(
            doc_id_column == self.closed_case_id,
            month_column == '2018-03-01',
        ).count())

        # in april the case should exist, be flagged as pregnant, and there are 2 forms
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            month_column == '2018-04-01'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(2, row.fu_forms_in_month)
        self.assertEqual(1, row.any_fu_forms_in_month)
        # the closed case should now be absent
        self.assertEqual(0, aggregate_query.filter(
            doc_id_column == self.closed_case_id,
            month_column == '2018-04-01',
        ).count())

    def test_weekly_aggregation(self):
        # generate our table
        aggregate_table_adapter = get_indicator_adapter(self.weekly_aggregate_table_definition)
        aggregate_table_adapter.rebuild_table()

        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_weekly_results()

        # confirm it's also idempotent
        populate_aggregate_table_data(aggregate_table_adapter)
        self._check_weekly_results()

    def _check_weekly_results(self):
        aggregate_table_adapter = get_indicator_adapter(self.weekly_aggregate_table_definition)
        aggregate_table = aggregate_table_adapter.get_table()
        aggregate_query = aggregate_table_adapter.get_query_object()

        doc_id_column = aggregate_table.c['doc_id']
        week_column = aggregate_table.c['week']
        # before december the case should not exist
        self.assertEqual(0, aggregate_query.filter(
            doc_id_column == self.case_id,
            week_column <= '2017-12-17'
        ).count())

        # from the monday in december where the case was opened, it case should exist,
        # but should not be flagged as pregnant
        for monday in ('2017-12-18', '2017-12-25', '2018-01-01'):
            row = aggregate_query.filter(
                doc_id_column == self.case_id,
                week_column == monday
            ).one()
            self.assertEqual(self.case_name, row.name)
            self.assertEqual(1, row.open_in_month)
            self.assertEqual(0, row.pregnant_in_month)
            self.assertEqual(None, row.fu_forms_in_month)

        # from monday of the EDD the case should exist, and be flagged as pregnant
        for monday in ('2018-01-15', '2018-01-22', '2018-01-29'):
            row = aggregate_query.filter(
                doc_id_column == self.case_id,
                week_column == monday,
            ).one()
            self.assertEqual(1, row.open_in_month)
            self.assertEqual(1, row.pregnant_in_month)
            self.assertEqual(None, row.fu_forms_in_month)

        # the monday of the march visit, the should exist, be flagged as pregnant, and there is a form
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            week_column == '2018-03-12'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(1, row.fu_forms_in_month)

        # but the monday after there are no forms again
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            week_column == '2018-03-19'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(None, row.fu_forms_in_month)

        # the week of the april 9, the case should exist, be flagged as pregnant, and there are 2 forms
        row = aggregate_query.filter(
            doc_id_column == self.case_id,
            week_column == '2018-04-09'
        ).one()
        self.assertEqual(1, row.open_in_month)
        self.assertEqual(1, row.pregnant_in_month)
        self.assertEqual(2, row.fu_forms_in_month)
