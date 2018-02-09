from __future__ import absolute_import
from datetime import datetime
import mock

from django.test.testcases import TestCase

from casexml.apps.stock.models import StockTransaction, StockReport

from corehq.apps.locations.forms import LocationFormSet

from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues,\
    OrganizationSummary, GroupSummary, PendingReportingDataRecalculation, ReportRun
from custom.ilsgateway.tanzania.warehouse.updater import process_facility_warehouse_data, \
    process_non_facility_warehouse_data
from custom.ilsgateway.tasks import report_run
from custom.ilsgateway.tests.handlers.utils import prepare_domain, create_products
from custom.ilsgateway.utils import make_loc, create_stock_report

TEST_DOMAIN = 'report-runner-test'


class TestReportRunner(TestCase):

    @classmethod
    def tearDownClass(cls):
        SupplyPointStatus.objects.all().delete()
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()
        cls.domain.delete()
        super(TestReportRunner, cls).tearDownClass()

    @classmethod
    def setUpClass(cls):
        super(TestReportRunner, cls).setUpClass()
        cls.domain = prepare_domain(TEST_DOMAIN)

        cls.mohsw = make_loc(code='mohsw', name='mohsw', domain=TEST_DOMAIN, type='MOHSW')

        cls.region1 = make_loc(code='region1', name='Test Region 1', domain=TEST_DOMAIN,
                               type='REGION', parent=cls.mohsw)
        cls.region2 = make_loc(code='region2', name='Test Region 2', domain=TEST_DOMAIN,
                               type='REGION', parent=cls.mohsw)

        cls.district1 = make_loc(code='district1', name='Test District 1', domain=TEST_DOMAIN,
                                 type='DISTRICT', parent=cls.region1)
        cls.district2 = make_loc(code='district2', name='Test District 2', domain=TEST_DOMAIN,
                                 type='DISTRICT', parent=cls.region2)

        cls.facility1 = make_loc(code='facility1', name='Test Facility 1', domain=TEST_DOMAIN,
                                 type='FACILITY', parent=cls.district1, metadata={'group': 'A'})
        cls.facility2 = make_loc(code='facility2', name='Test Facility 2', domain=TEST_DOMAIN,
                                 type='FACILITY', parent=cls.district2, metadata={'group': 'C'})

        create_products(cls, TEST_DOMAIN, ['dx', 'al', 'ab'])

        date = datetime(2015, 9, 2)
        create_stock_report(cls.facility1, {'dx': 10, 'al': 0, 'ab': 15}, date)
        create_stock_report(cls.facility2, {'dx': 10, 'al': 20, 'ab': 15}, date)

        SupplyPointStatus.objects.create(
            status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
            status_value=SupplyPointStatusValues.RECEIVED,
            status_date=date,
            location_id=cls.facility1.get_id
        )

        SupplyPointStatus.objects.create(
            status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
            status_value=SupplyPointStatusValues.SUBMITTED,
            status_date=date,
            location_id=cls.facility2.get_id
        )

    def _move_location(self, location, new_parent_id):
        form = LocationFormSet(
            location.sql_location,
            request_user=mock.MagicMock(),
            is_new=False,
            bound_data={
                'name': location.name,
                'parent_id': new_parent_id,
                'location_type': location.location_type_object,
                'data-field-group': location.metadata['group']
            }
        )
        form.save()

    def _change_group(self, location, group):
        form = LocationFormSet(
            location.sql_location,
            request_user=mock.MagicMock(),
            is_new=False,
            bound_data={
                'name': location.name,
                'data-field-group': group,
                'location_type': location.location_type_object,
                'parent_id': location.parent_location_id
            }
        )
        form.save()

    def setUp(self):
        super(TestReportRunner, self).setUp()
        OrganizationSummary.objects.all().delete()
        ReportRun.objects.all().delete()

    def test_report_runner(self):
        d = datetime(2015, 9, 1)
        with mock.patch('custom.ilsgateway.tanzania.warehouse.updater.default_start_date', return_value=d), \
                mock.patch('custom.ilsgateway.tasks.default_start_date', return_value=d), \
                mock.patch('custom.ilsgateway.tasks.get_start_date', return_value=d):
            report_run(TEST_DOMAIN)
            self.assertEqual(OrganizationSummary.objects.filter(date__lte=datetime(2015, 9, 3)).count(), 7)

            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.district1.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 1
            )
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.district2.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 1
            )

            self._move_location(self.facility1, self.district2.get_id)

            pr = PendingReportingDataRecalculation.objects.filter(sql_location=self.facility1.sql_location).first()
            self.assertEqual(pr.type, 'parent_change')
            self.assertDictEqual(
                pr.data,
                {'previous_parent': self.district1.get_id, 'current_parent': self.district2.get_id}
            )

            report_run(TEST_DOMAIN)
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.district1.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 0
            )
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.region1.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 0
            )
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.district2.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 2
            )
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.region2.get_id,
                    title=SupplyPointStatusTypes.SOH_FACILITY
                ).first().total, 2
            )

    def test_report_runner2(self):
        d = datetime(2015, 9, 1)
        with mock.patch('custom.ilsgateway.tanzania.warehouse.updater.default_start_date', return_value=d), \
                mock.patch('custom.ilsgateway.tasks.default_start_date', return_value=d),\
                mock.patch('custom.ilsgateway.tasks.get_start_date', return_value=d):
            report_run(TEST_DOMAIN)
            self.assertEqual(OrganizationSummary.objects.filter(date__lte=datetime(2015, 9, 3)).count(), 7)
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.facility1.get_id,
                    title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                ).first().total, 1
            )

            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.facility2.get_id,
                    title=SupplyPointStatusTypes.R_AND_R_FACILITY
                ).first().total, 1
            )

            self._change_group(self.facility1, 'C')
            pr = PendingReportingDataRecalculation.objects.filter(sql_location=self.facility1.sql_location).first()
            self.assertEqual(pr.type, 'group_change')
            self.assertDictEqual(pr.data, {'previous_group': 'A', 'current_group': 'C'})

            report_run(TEST_DOMAIN)
            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.facility1.get_id,
                    title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                ).first().total, 0
            )

            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.facility1.get_id,
                    title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                ).first().total, 1
            )

            self.assertEqual(
                GroupSummary.objects.filter(
                    org_summary__location_id=self.facility2.get_id,
                    title=SupplyPointStatusTypes.R_AND_R_FACILITY
                ).first().total, 1
            )

    def test_location_created_after_facility_processing(self):
        start_date = datetime(2015, 9, 1)
        end_date = datetime.utcnow()
        with mock.patch('custom.ilsgateway.tanzania.warehouse.updater.default_start_date', return_value=start_date), \
                mock.patch('custom.ilsgateway.tasks.default_start_date', return_value=start_date), \
                mock.patch('custom.ilsgateway.tasks.get_start_date', return_value=start_date):
            run = ReportRun.objects.create(start=start_date, end=end_date,
                                           start_run=datetime.utcnow(), domain=self.domain.name)

            process_facility_warehouse_data(self.facility1, start_date, end_date, run)

            facility = make_loc(code='new_facility', name='New Facility', domain=self.domain.name,
                                type='FACILITY', parent=self.district1, metadata={'group': 'A'})

            process_non_facility_warehouse_data(self.district1, start_date, end_date, run)
            self.assertEqual(OrganizationSummary.objects.filter(date__lte=datetime(2015, 9, 3)).count(), 2)

            facility.delete()
