from corehq.apps.reports.graph_models import PieChart
from corehq.apps.commtrack.models import SQLProduct
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, DeliveryGroups, \
    ProductAvailabilityData, ProductAvailabilityDashboardChart


class ILSData(object):
    show_table = False
    show_chart = True

    chart_config = {
        'on_time': {
            'color': 'green',
            'display': 'Submitted On Time'
        },
        'late': {
            'color': 'orange',
            'display': 'Submitted Late'
        },
        'not_submitted': {
            'color': 'red',
            'display': "Haven't Submitted "
        },
        'del_received': {
            'color': 'green',
            'display': 'Delivery Received',
        },
        'del_not_received': {
            'color': 'red',
            'display': 'Delivery Not Received',
        },
        'sup_received': {
            'color': 'green',
            'display': 'Supervision Received',
        },
        'sup_not_received': {
            'color': 'red',
            'display': 'Supervision Not Received',
        },
        'not_responding': {
            'color': '#8b198b',
            'display': "Didn't Respond"
        },
    }
    vals_config = {
        SupplyPointStatusTypes.SOH_FACILITY: ['on_time', 'late', 'not_submitted', 'not_responding'],
        SupplyPointStatusTypes.DELIVERY_FACILITY: ['del_received', 'del_not_received', 'not_responding'],
        SupplyPointStatusTypes.R_AND_R_FACILITY: ['on_time', 'late', 'not_submitted', 'not_responding'],
        SupplyPointStatusTypes.SUPERVISION_FACILITY: ['sup_received', 'sup_not_received', 'not_responding']
    }

    def __init__(self, config=None, css_class='row_chart'):
        self.config = config or {}
        self.css_class = css_class

    @property
    def headers(self):
        raise []

    @property
    def rows(self):
        raise NotImplementedError

    @property
    def charts(self):
        data = self.rows

        ret = []
        sum_all = 0
        colors = []
        if data:
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    sum_all = sum_all + getattr(data, key)
            for key in self.vals_config[data.title]:
                if getattr(data, key, None):
                    entry = {}
                    entry['value'] = float(getattr(data, key)) * 100 / float((sum_all or 1))
                    colors.append(self.chart_config[key]['color'])
                    entry['label'] = self.chart_config[key]['display']
                    params = (
                        entry['value'],
                        getattr(data, key), entry['label'],
                        self.config['startdate'].strftime("%b %Y")
                    )
                    entry['description'] = "%.2f%% (%d) %s (%s)" % params

                    ret.append(entry)
        return [PieChart('', '', ret, color=colors)]


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
                supply_point=self.config['org_summary'].supply_point)
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


class ILSMixin(object):

    @property
    def report_facilities_url(self):
        return None

    @property
    def report_stockonhand_url(self):
        return None

    @property
    def report_rand_url(self):
        return None

    @property
    def report_supervision_url(self):
        return None

    @property
    def report_delivery_url(self):
        return None

    @property
    def report_unrecognizedmessages_url(self):
        return None
