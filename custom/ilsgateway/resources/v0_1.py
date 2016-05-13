from corehq.apps.locations.resources.v0_1 import LocationResource


class ILSLocationResource(LocationResource):

    def child_queryset(self, domain, include_inactive, parent):
        return parent.sql_location.get_children().filter(
            location_type__administrative=True,
            is_archived=False
        )

    class Meta(LocationResource.Meta):
        resource_name = 'ils_location'
