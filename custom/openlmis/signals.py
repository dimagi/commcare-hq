from django.dispatch import receiver
from corehq import Domain
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.models import Program
from corehq.apps.commtrack.signals import supply_point_modified, requisition_modified
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, requisition_approved, approve_requisition, requisition_receipt, delivery_update, sync_stock_data_to_openlmis


@receiver(supply_point_modified)
def supply_point_updated(sender, supply_point, created, **kwargs):
    project = Domain.get_by_name(supply_point.domain)
    if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:

        # check if supply_point is of 'chw type'
        if supply_point.location and supply_point.location.type is 'chw':

            #check if supply_point is linked to an OpenLMIS facility
            if supply_point.location.parent and supply_point.location.parent.external_id:
                endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
                sync_supply_point_to_openlmis(supply_point, endpoint)


@receiver(requisition_approved)
def approve_requisitions(sender, requisitions, **kwargs):
    if requisitions and requisitions[0].requisition_status is RequisitionStatus.APPROVED:
        project = Domain.get_by_name(requisitions[0].domain)
        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
            approve_requisition(requisitions, endpoint)


@receiver(requisition_receipt)
def confirm_delivery(sender, requisitions, **kwargs):
    if requisitions and requisitions[0].requisition_status is RequisitionStatus.RECEIVED:
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
        for rq in cases:
            product = rq.get_product()
            products.append({'productCode': product.code,
                             'beginningBalance': product.beginningBalance,
                             'quantityReceived': product.quantityReceived,
                             'quantityDispensed': product.quantityDispensed,
                             'lossesAndAdjustments': product.lossesAndAdjustments,
                             'newPatientCount': product.newPatientCount,
                             'stockOnHand': product.stockOnHand,
                             'stockOutDays': product.stockOutDays,
                             'quantityRequested': product.quantityRequested,
                             'reasonForRequestedQuantity': product.reasonForRequestedQuantity,
                             'remarks': product.remarks})

        stock_data = {  'agentCode': agentCode,
                        'programCode': programCode,
                        'products': products
        }
        response = sync_stock_data_to_openlmis(submission=stock_data, openlmis_endpoint=endpoint)

        if response['requisitionId'] is not None:
            for rq in cases:
                rq.external_id = response['requisitionId']
                rq.save()
