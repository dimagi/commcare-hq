from datetime import datetime
from django.test.testcases import TestCase
import mock
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.locations.forms import LocationForm

from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues,\
    OrganizationSummary, GroupSummary
from custom.ilsgateway.tasks import report_run
from custom.ilsgateway.tests.handlers.utils import prepare_domain, create_products
from custom.ilsgateway.utils import make_loc, create_stock_report
from custom.logistics.models import StockDataCheckpoint

TEST_DOMAIN = 'report-runner-test'


class TestReportRunner(TestCase):

    @classmethod
    def tearDownClass(cls):
        SupplyPointStatus.objects.all().delete()
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()

    @classmethod
    def setUpClass(cls):
        prepare_domain(TEST_DOMAIN)

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
        StockDataCheckpoint.objects.create(
            domain=TEST_DOMAIN,
            api='test',
            date=date,
            limit=1000,
            offset=0
        )

    def _move_location(self, location, new_parent_id):
        form = LocationForm(
            location,
            bound_data={'name': location.name, 'parent_id': new_parent_id}
        )
        form.save()

    def test_report_runner(self):
        with mock.patch('custom.ilsgateway.tanzania.warehouse.updater.default_start_date',
                        return_value=datetime(2015, 9, 1)):
            report_run(TEST_DOMAIN)

            self.assertEqual(OrganizationSummary.objects.count(), 7)
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
