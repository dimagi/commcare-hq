from django.urls import re_path as url
from tastypie import fields
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpNotFound
from . import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
)
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.users.role_utils import get_commcare_analytics_access_for_user_domain
from corehq import toggles
from corehq.apps.users.models import CouchUser


class CommCareAnalyticsUserResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

    roles = fields.ListField()
    permissions = fields.DictField()

    class Meta(CustomResourceMeta):
        resource_name = 'analytics-roles'
        detail_allowed_methods = ['get']

    def dehydrate(self, bundle):
        cca_access = get_commcare_analytics_access_for_user_domain(bundle.obj, bundle.request.domain)

        bundle.data['roles'] = cca_access['roles']
        bundle.data['permissions'] = cca_access['permissions']

        return bundle

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        if not toggles.SUPERSET_ANALYTICS.enabled(domain):
            raise ImmediateHttpResponse(
                HttpNotFound()
            )

        user = CouchUser.get_by_username(bundle.request.user.username)

        if not (user and user.is_member_of(domain) and user.is_active):
            return None
        return user

    def prepend_urls(self):
        # We're overriding the default "list" view to redirect to "detail" view since
        # we already know the user through OAuth.
        return [
            url(r"^$", self.wrap_view('dispatch_detail'), name='api_dispatch_detail'),
        ]
