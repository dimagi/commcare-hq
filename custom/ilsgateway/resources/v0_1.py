from __future__ import absolute_import
from corehq.apps.api.resources.auth import LoginAndDomainAuthentication
from corehq.apps.locations.resources.v0_1 import LocationResource


class ILSLocationResource(LocationResource):

    def child_queryset(self, domain, include_inactive, parent):
        return parent.sql_location.get_children().filter(
            location_type__administrative=True,
            is_archived=False
        )

    class Meta(LocationResource.Meta):
        authentication = LoginAndDomainAuthentication(allow_session_auth=True)
        resource_name = 'ils_location'
