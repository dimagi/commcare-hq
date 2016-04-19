from django.db.models.aggregates import Avg, Max
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
        if 'data_config' in self.config:
            data_config = self.config['data_config']
            submitted_on_time = data_config.rr_data_total.get(('on_time', 'submitted'), 0)
            not_submitted_on_time = data_config.rr_data_total.get(('on_time', 'not_submitted'), 0)
            submitted_late = data_config.rr_data_total.get(('late', 'submitted'), 0)
            not_submitted_late = data_config.rr_data_total.get(('late', 'not_submitted'), 0)
            return[GroupSummary(
                title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                responded=submitted_on_time + not_submitted_on_time + submitted_late + not_submitted_late,
                on_time=submitted_on_time,
                complete=submitted_on_time + submitted_late,
                total=data_config.rr_data_total.get('total', 0)
            )]
        if self.config['org_summary']:
            rr = GroupSummary.objects.filter(
                title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                org_summary__in=self.config['org_summary']
            ).aggregate(Avg('responded'), Avg('on_time'), Avg('complete'), Max('total'))

            return [GroupSummary(
                title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                responded=rr['responded__avg'],
                on_time=rr['on_time__avg'],
                complete=rr['complete__avg'],
                total=rr['total__max']
            )]
        return [GroupSummary(
            title=SupplyPointStatusTypes.R_AND_R_FACILITY,
            responded=0,
            on_time=0,
            complete=0,
            total=0
        )]


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
                    'total': data[0] - (data[1] + data[2]),
                    'complete': 0
                }

            org_summary = self.config['org_summary'][0]
            total = org_summary.total_orgs
            avg_lead_time = org_summary.average_lead_time_in_days
            if avg_lead_time:
                avg_lead_time = "%.1f" % avg_lead_time

            endmonth = self.config['enddate'].month
            dg = DeliveryGroups(month=endmonth)

            rr_data = RandRSubmissionData(config=self.config).rows[0]
            delivery_data = DeliverySubmissionData(config=self.config).rows[0]

            submitting_group = dg.current_submitting_group(month=endmonth)
            processing_group = dg.current_processing_group(month=endmonth)
            delivery_group = dg.current_delivering_group(month=endmonth)

            (rr_complete, rr_total) = (rr_data.complete, rr_data.total) if rr_data else (0, 0)
            if delivery_data:
                (delivery_complete, delivery_total) = (delivery_data.complete, delivery_data.total)
            else:
                (delivery_complete, delivery_total) = (0, 0)

            processing_numbers = prepare_processing_info([total, rr_total, delivery_total])

            return {
                "processing_total": processing_numbers['total'],
                "processing_complete": processing_numbers['complete'],
                "submitting_total": rr_total,
                "submitting_complete": int(rr_complete),
                "delivery_total": delivery_total,
                "delivery_complete": int(delivery_complete),
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

        if 'data_config' in self.config:
            data_config = self.config['data_config']
            late = data_config.soh_data_total.get('late', 0)
            on_time = data_config.soh_data_total.get('on_time', 0)
            soh_data.append(GroupSummary(
                title=SupplyPointStatusTypes.SOH_FACILITY,
                responded=late + on_time,
                on_time=on_time,
                complete=late + on_time,
                total=len(data_config.descendants)
            ))
            return soh_data

        if self.config['org_summary']:
            try:
                sohs = GroupSummary.objects.filter(
                    title=SupplyPointStatusTypes.SOH_FACILITY,
                    org_summary__in=self.config['org_summary']
                ).aggregate(Avg('responded'), Avg('on_time'), Avg('complete'), Max('total'))

                soh_data.append(GroupSummary(
                    title=SupplyPointStatusTypes.SOH_FACILITY,
                    responded=sohs['responded__avg'],
                    on_time=sohs['on_time__avg'],
                    complete=sohs['complete__avg'],
                    total=sohs['total__max']
                ))
            except GroupSummary.DoesNotExist:
                return soh_data
        return soh_data


class DeliverySubmissionData(ILSData):
    title = 'Delivery Submission'
    slug = 'delivery_submission'

    @property
    def rows(self):
        del_data = []
        if 'data_config' in self.config:
            data_config = self.config['data_config']
            delivered = data_config.delivery_data_total.get('received', 0)
            not_delivered = data_config.delivery_data_total.get('not_received', 0)
            del_data.append(GroupSummary(
                title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                responded=delivered + not_delivered,
                on_time=delivered + not_delivered,
                complete=delivered,
                total=data_config.delivery_data_total.get('total', 0)
            ))
            return del_data

        if self.config['org_summary']:
            try:
                data = GroupSummary.objects.filter(
                    title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                    org_summary__in=self.config['org_summary']
                ).aggregate(Avg('responded'), Avg('on_time'), Avg('complete'), Max('total'))

                del_data.append(GroupSummary(
                    title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                    responded=data['responded__avg'],
                    on_time=data['on_time__avg'],
                    complete=data['complete__avg'],
                    total=data['total__max']
                ))
            except GroupSummary.DoesNotExist:
                return del_data
        return del_data


class ILSMultiBarChart(MultiBarChart):
    template_partial = 'ilsgateway/partials/ils_multibar_chart.html'


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
                location_id=self.config['org_summary'][0].location_id,
                product__in=self.config['products']
            ).values('product').annotate(
                with_stock=Avg('with_stock'),
                without_data=Avg('without_data'),
                without_stock=Avg('without_stock'),
                total=Max('total')
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
                    prd_code = SQLProduct.objects.get(product_id=product['product']).code
                    if k == 'No Stock Data':
                        datalist.append([prd_code, product['without_data']])
                    elif k == 'Stocked out':
                        datalist.append([prd_code, product['without_stock']])
                    elif k == 'Not Stocked out':
                        datalist.append([prd_code, product['with_stock']])
                ret_data.append({'color': chart_config.label_color[k], 'label': k, 'data': datalist})
            return ret_data

        chart = ILSMultiBarChart('', x_axis=Axis('Products'), y_axis=Axis('', format='d'))
        chart.tooltipFormat = ' on '
        chart.rotateLabels = -45
        chart.marginBottom = 60
        chart.marginRight = 20
        chart.marginLeft = 50
        chart.height = 350
        chart.stacked = self.chart_stacked
        for row in convert_product_data_to_stack_chart(product_availability, product_dashboard):
            chart.add_dataset(row['label'], [
                {'x': r[0], 'y': int(round(r[1]))}
                for r in sorted(row['data'], key=lambda x: x[0])], color=row['color']
            )
        return [chart]
