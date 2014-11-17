from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter, MonthFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, DeliveryGroups, \
    ProductAvailabilityData, ProductAvailabilityDashboardChart
from custom.ilsgateway.tanzania.reports import ILSData
from custom.ilsgateway.tanzania.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized


class RandRSubmissionData(ILSData):
    title = 'R&R Submission'
    slug = 'rr_submission'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rr_data = []
        if self.config['org_summary']:
            rr_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                               org_summary=self.config['org_summary'])
        return rr_data


class DistrictSummaryData(ILSData):
    title = 'District Summary'
    slug = 'district_summary'
    show_table = True
    show_chart = False

    @property
    def headers(self):
        return []

    @property
    def rows(self):

        if self.config['org_summary']:

            def prepare_processing_info(data):
                numbers = {}
                numbers['total'] = data[0] - (data[1].total + data[2].total)
                numbers['complete'] = 0
                return numbers

            org_summary = self.config['org_summary']
            total = org_summary.total_orgs
            avg_lead_time = org_summary.average_lead_time_in_days
            if avg_lead_time:
                avg_lead_time = "%.1f" % avg_lead_time

            endmonth = self.config['enddate'].month
            dg = DeliveryGroups(month=endmonth)

            rr_data = RandRSubmissionData(config=self.config).rows
            delivery_data = DeliverySubmissionData(config=self.config).rows

            submitting_group = dg.current_submitting_group(month=endmonth)
            processing_group = dg.current_processing_group(month=endmonth)
            delivery_group = dg.current_delivering_group(month=endmonth)

            processing_numbers = prepare_processing_info([total, rr_data, delivery_data])

            return {
                "processing_total": processing_numbers['total'],
                "processing_complete": processing_numbers['complete'],
                "submitting_total": rr_data.total,
                "submitting_complete": rr_data.complete,
                "delivery_total": delivery_data.total,
                "delivery_complete": delivery_data.complete,
                "delivery_group": delivery_group,
                "submitting_group": submitting_group,
                "processing_group": processing_group,
                "total": total,
                "avg_lead_time": avg_lead_time,
            }
        else:
            return None


class SohSubmissionData(ILSData):
    title = 'SOH Submission'
    slug = 'soh_submission'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        soh_data = []
        if self.config['org_summary']:
            soh_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SOH_FACILITY,
                                                org_summary=self.config['org_summary'])
        return soh_data


class DeliverySubmissionData(ILSData):
    title = 'Delivery Submission'
    slug = 'delivery_submission'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        del_data = []
        if self.config['org_summary']:
            del_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                org_summary=self.config['org_summary'])
        return del_data


class ProductAvailabilitySummary(ILSData):
    title = 'Product Availability Summary'
    slug = 'product_availability'
    css_class = 'row_chart_all'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        product_availability = []
        if self.config['org_summary']:
            product_availability = ProductAvailabilityData.objects.filter(
                date__range=(self.config['startdate'], self.config['enddate']),
                supply_point=self.config['org_summary'].supply_point
            )
        return product_availability

    @property
    def charts(self):
        product_dashboard = ProductAvailabilityDashboardChart()
        product_availability = self.rows

        def convert_product_data_to_stack_chart(rows, chart_config):
            ret_data = []
            for k in ['Stocked out', 'Not Stocked out', 'No Stock Data']:
                datalist = []
                for product in rows:
                    prd_code = SQLProduct.objects.get(product_id=product.product).code
                    if k == 'No Stock Data':
                        datalist.append([prd_code, product.without_data])
                    elif k == 'Stocked out':
                        datalist.append([prd_code, product.without_stock])
                    elif k == 'Not Stocked out':
                        datalist.append([prd_code, product.with_stock])
                ret_data.append({'color': chart_config.label_color[k], 'label': k, 'data': datalist})
            return ret_data

        chart = MultiBarChart('', x_axis=Axis('Products'), y_axis=Axis(''))
        chart.rotateLabels = -45
        chart.marginBottom = 120
        chart.stacked = True
        for row in convert_product_data_to_stack_chart(product_availability, product_dashboard):
            chart.add_dataset(row['label'], [{'x': r[0], 'y': r[1]}
                                             for r in sorted(row['data'], key=lambda x: x[0])], color=row['color'])
        return [chart]


class DashboardReport(MultiReport):
    title = "Dashboard report"
    fields = [AsyncLocationFilter, MonthFilter, YearFilter]
    name = "Dashboard report"
    slug = 'ils_dashboard_report'

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [RandRSubmissionData(config=config),
                DistrictSummaryData(config=config),
                SohSubmissionData(config=config),
                DeliverySubmissionData(config=config),
                ProductAvailabilitySummary(config=config)]
