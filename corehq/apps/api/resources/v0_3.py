from couchdbkit import ResourceNotFound
from corehq.apps.cloudcare.api import es_filter_cases
from tastypie import fields

from casexml.apps.case.models import CommCareCase

from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import v0_2, v0_1
from corehq.apps.api.resources import DomainSpecificResourceMixin
from corehq.apps.api.util import object_does_not_exist
import couchforms
from couchforms.models import XFormArchived


class CaseListFilters(object):
    format = 'json'
    
    def __init__(self, params):
        self.filters = dict((k, v) for k, v in params.items())

        #hacky hack for v0.3.
        #for v0.4, the API will explicitly require name and type
        #for this version, magically behind the scenes override the query for case_name and case_type to be name, type
        #note, on return output, the name will return as case_name, and type will return as case_type

        if 'case_name' in self.filters:
            self.filters['name'] = self.filters['case_name']
            del(self.filters['case_name'])
        if 'case_type' in self.filters:
            self.filters['type'] = self.filters['case_type']
            del(self.filters['case_type'])

        if 'format' in self.filters:
            self.format = self.filters['format']
            del self.filters['format']

        if 'order_by' in self.filters:
            del self.filters['order_by']

class CommCareCaseResource(v0_2.CommCareCaseResource, DomainSpecificResourceMixin):
    
    # in v2 this can't be null, but in v3 it can
    user_id = fields.CharField(attribute='user_id', null=True)

    # in v2 the bundle.obj is not actually a CommCareCase object but just a dict_object around a CaseAPIResult
    # so there is no 'get_json'
    def dehydrate_properties(self, bundle):
        return bundle.obj.get_json(lite=True)['properties']

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_json(lite=True)['indices']

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(CommCareCase, kwargs['pk'], kwargs['domain'])
    
    def obj_get_list(self, bundle, domain, **kwargs):
        filters = CaseListFilters(bundle.request.GET)
        return es_filter_cases(domain, filters=filters.filters)

    
class XFormInstanceResource(v0_1.XFormInstanceResource, DomainSpecificResourceMixin):
    archived = fields.CharField(readonly=True)

    def dehydrate_archived(self, bundle):
        return isinstance(bundle.obj, XFormArchived)
    
    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        doc_id = kwargs['pk']
        doc_type = 'XFormInstance'
        # Logic borrowed from util.get_object_or_not_exist
        try:
            doc = couchforms.fetch_and_wrap_form(doc_id)
            if doc and doc.domain == domain:
                return doc
        except ResourceNotFound:
            pass # covered by the below
        except AttributeError:
            # there's a weird edge case if you reference a form with a case id
            # that explodes on the "version" property. might as well swallow that
            # too.
            pass
        raise object_does_not_exist(doc_type, doc_id)
