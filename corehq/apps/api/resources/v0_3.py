from __future__ import absolute_import
from __future__ import unicode_literals

import six
from tastypie import fields
from tastypie.exceptions import BadRequest

from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import es_search, ElasticAPIQuerySet, CaseES
from corehq.apps.api.models import ESCase
from corehq.apps.api.resources import DomainSpecificResourceMixin
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import object_does_not_exist, get_obj
from corehq.apps.users.models import Permissions
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from no_exceptions.exceptions import Http400

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.
MOCK_CASE_ES = None


class CommCareCaseResource(HqBaseResource, DomainSpecificResourceMixin):
    type = "case"
    id = fields.CharField(attribute='case_id', readonly=True, unique=True)
    case_id = id
    user_id = fields.CharField(attribute='user_id', null=True)
    date_modified = fields.CharField(attribute='date_modified', default="1900-01-01")
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    server_date_modified = fields.CharField(attribute='server_date_modified', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_date_opened', null=True)

    xform_ids = fields.ListField(attribute='xform_ids')

    properties = fields.DictField()

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_properties_in_api_format()

    indices = fields.DictField()

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_index_map()

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).case_id
        }

    def case_es(self, domain):
        # Note that CaseES is used only as an ES client, for `run_query` against the proper index
        return MOCK_CASE_ES or CaseES(domain)

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        try:
            return CaseAccessors(kwargs['domain']).get_case(case_id)
        except CaseNotFound:
            raise object_does_not_exist("CommCareCase", case_id)

    def obj_get_list(self, bundle, domain, **kwargs):
        try:
            es_query = es_search(bundle.request, domain)
        except Http400 as e:
            raise BadRequest(six.text_type(e))

        return ElasticAPIQuerySet(
            payload=es_query,
            model=ESCase,
            es_client=self.case_es(domain)
        ).order_by('server_modified_on')

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = CommCareCase
        resource_name = 'case'
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
