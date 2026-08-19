from tastypie import fields
from tastypie.exceptions import BadRequest

from corehq.apps.api.es import CaseESView, ElasticAPIQuerySet, es_query_from_get_params
from corehq.apps.api.models import ESCase
from corehq.apps.api.resources import (
    DomainSpecificResourceMixin,
    HqBaseResource,
)
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_obj, object_does_not_exist
from corehq.apps.users.models import HqPermissions
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from no_exceptions.exceptions import Http400


class CommCareCaseResource(HqBaseResource, DomainSpecificResourceMixin):
    type = "case"
    id = fields.CharField(
        attribute='case_id',
        readonly=True,
        unique=True,
        help_text='Case UUID.',
    )
    case_id = id
    user_id = fields.CharField(
        attribute='user_id',
        null=True,
        help_text='UUID of the user that last modified the case.',
    )
    date_modified = fields.CharField(attribute='date_modified', default="1900-01-01")
    closed = fields.BooleanField(
        attribute='closed',
        help_text='Whether the case is closed.',
    )
    date_closed = fields.CharField(
        attribute='closed_on',
        null=True,
        help_text='Date and time the case was closed, or null if the '
                  'case is open.',
    )

    server_date_modified = fields.CharField(attribute='server_date_modified', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_date_opened', null=True)

    xform_ids = fields.ListField(
        attribute='xform_ids',
        help_text='UUIDs of the forms that have updated this case.',
    )

    properties = fields.DictField(
        help_text='Case property values, including special predefined '
                  'properties (case_name, case_type, external_id, '
                  'owner_id, date_opened) and any user-defined dynamic '
                  'properties.',
    )

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_properties_in_api_format()

    indices = fields.DictField(
        help_text='References to other cases linked to this case, keyed '
                  'by index identifier, each giving the related '
                  'case_type and case_id.',
    )

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_index_map()

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).case_id
        }

    def case_es(self, domain):
        # Note that CaseESView is used only as an ES client, for `run_query` against the proper index
        return CaseESView(domain)

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        try:
            return CommCareCase.objects.get_case(case_id, kwargs['domain'])
        except CaseNotFound:
            raise object_does_not_exist("CommCareCase", case_id)

    def obj_get_list(self, bundle, domain, **kwargs):
        try:
            es_query = es_query_from_get_params(bundle.request.GET, domain, doc_type='case')
        except Http400 as e:
            raise BadRequest(str(e))

        return ElasticAPIQuerySet(
            payload=es_query,
            model=ESCase,
            es_client=self.case_es(domain)
        ).order_by('server_modified_on')

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_data)
        object_class = ESCase
        resource_name = 'case'
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
