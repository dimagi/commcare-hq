from django.dispatch import receiver
from corehq import Domain
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.models import Program
from corehq.apps.commtrack.signals import supply_point_modified, requisition_modified, send_notifications
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, requisition_approved, approve_requisition, requisition_receipt, delivery_update, sync_stock_data_to_openlmis, sync_requisition_from_openlmis
import logging

@receiver(supply_point_modified)
def supply_point_updated(sender, supply_point, created, **kwargs):
    project = Domain.get_by_name(supply_point.domain)
    if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
        # check if supply_point is of 'chw type'
        if supply_point.location and supply_point.location.location_type == "chw":
            #check if supply_point is linked to an OpenLMIS facility
            if supply_point.location.lineage and len(supply_point.location.lineage) > 0:
                endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
                sync_supply_point_to_openlmis(supply_point, endpoint, created)

@receiver(requisition_approved)
def approve_requisitions(sender, requisitions, **kwargs):
    if requisitions and requisitions[0].requisition_status == RequisitionStatus.APPROVED:
        project = Domain.get_by_name(requisitions[0].domain)
        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
            approve_requisition(requisitions, endpoint)


@receiver(requisition_receipt)
def confirm_delivery(sender, requisitions, **kwargs):
    if requisitions and requisitions[0].requisition_status == RequisitionStatus.RECEIVED:
        project = Domain.get_by_name(requisitions[0].domain)
        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
            delivery_update(requisitions, endpoint)


@receiver(requisition_modified)
def stock_data_submission(sender, cases, endpoint=None, **kwargs):
    project = Domain.get_by_name(cases[0].domain)

    if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:

        if endpoint is None:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)

        # get agentCode and programCode - I assume all cases are part of the same program
        agentCode = (cases[0].get_supply_point_case()).location.site_code
        programCode = Program.get(cases[0].get_product().program_id).code

        products = []
        for case in cases:
            product = case.get_product()

            product_json = {'productCode': product.code}
            product_json['stockInHand'] = int(case.get_default_value())

            products.append(product_json)

        stock_data = {  'agentCode': agentCode,
                        'programCode': programCode,
                        'products': products
        }
        response = sync_stock_data_to_openlmis(submission=stock_data, openlmis_endpoint=endpoint)

        if response['requisitionId'] is not None:
            for case in cases:
                case.external_id = response['requisitionId']
                case.save()

            cases, send_notification = sync_requisition_from_openlmis(project.name, response['requisitionId'], endpoint)
            if send_notification:
                send_notifications(xform=None, cases=cases)