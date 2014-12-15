from custom.ilsgateway.tanzania import ILSData

from corehq.apps.commtrack.models import SQLProduct
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, DeliveryGroups, \
    ProductAvailabilityData, ProductAvailabilityDashboardChart


class RandRSubmissionData(ILSData):
    title = 'R&R Submission'
    slug = 'rr_submission'

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
    def rows(self):

        if self.config['org_summary']:

            def prepare_processing_info(data):
                return {
                    'total': data[0] - (data[1].total + data[2].total),
                    'complete': 0
                }

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
    def rows(self):
        del_data = []
        if self.config['org_summary']:
            del_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                org_summary=self.config['org_summary'])
        return del_data


class ProductAvailabilitySummary(ILSData):
    title = 'Product Availability'
    slug = 'product_availability'

    def __init__(self, config, css_class, chart_stacked=True):
        super(ProductAvailabilitySummary, self).__init__(config, css_class)
        self.chart_stacked = chart_stacked

    @property
    def rows(self):
        product_availability = []
        if self.config['org_summary']:
            product_availability = ProductAvailabilityData.objects.filter(
                date__range=(self.config['startdate'], self.config['enddate']),
                supply_point=self.config['org_summary'].supply_point,
                product__in=self.config['products'])
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
        chart.stacked = self.chart_stacked
        for row in convert_product_data_to_stack_chart(product_availability, product_dashboard):
            chart.add_dataset(row['label'], [
                {'x': r[0], 'y': r[1]}
                for r in sorted(row['data'], key=lambda x: x[0])], color=row['color']
            )
        return [chart]
