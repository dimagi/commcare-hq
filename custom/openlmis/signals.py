from django.dispatch import receiver, Signal
from casexml.apps.case.xform import get_case_updates
from corehq import Domain
from corehq.apps.commtrack.const import RequisitionStatus, SUPPLY_POINT_CASE_TYPE, is_supply_point_form
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.programs.models import Program
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, requisition_approved, approve_requisition, requisition_receipt, delivery_update, sync_stock_data_to_openlmis, sync_requisition_from_openlmis
from custom.requisitions.signals import send_notifications, requisition_modified


supply_point_modified = Signal(providing_args=['supply_point', 'created'])


def raise_supply_point_events(xform, cases):
    supply_points = [SupplyPointCase.wrap(c._doc) for c in cases if c.type == SUPPLY_POINT_CASE_TYPE]
    case_updates = get_case_updates(xform)
    for sp in supply_points:
        created = any(filter(lambda update: update.id == sp._id and update.creates_case(), case_updates))
        supply_point_modified.send(sender=None, supply_point=sp, created=created)


def supply_point_processing(sender, xform, cases, **kwargs):
    if is_supply_point_form(xform):
        raise_supply_point_events(xform, cases)


# note: this is commented out since no one is actually using this functionality
# if we want to reenable openlmis integrations we will need to uncomment it.
# the more likely scenario is that all of this code will be deleted sometime in the future.
# cases_received.connect(supply_point_processing)


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
