from django.dispatch import receiver
from corehq import Domain
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.signals import supply_point_modified
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, requisition_receipt


@receiver(supply_point_modified)
def supply_point_updated(sender, supply_point, created, **kwargs):
    project = Domain.get_by_name(supply_point.domain)
    if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
        endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
        sync_supply_point_to_openlmis(supply_point, endpoint)

@receiver(requisition_receipt)
def confirm_delivery(sender, requisitions, **kwargs):
    if requisitions and requisitions[0].requisition_status is RequisitionStatus.RECEIVED:
        project = Domain.get_by_name(requisitions[0].domain)
        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
            confirm_delivery(requisitions, endpoint)