from django.dispatch import receiver
from corehq import Domain
from corehq.apps.commtrack.signals import supply_point_modified
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import sync_supply_point_to_openlmis


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
