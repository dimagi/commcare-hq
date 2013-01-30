from corehq.apps.cloudcare.api import es_filter_cases
from . import v0_2 
from corehq.apps.api.resources.v0_2 import dict_object
from tastypie import fields

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

class CommCareCaseResource(v0_2.CommCareCaseResource):
    
    # in v2 this can't be null, but in v3 it can
    user_id = fields.CharField(attribute='user_id', null=True)
    
    def obj_get_list(self, request, domain, **kwargs):
        filters = CaseListFilters(request.GET)
        return map(dict_object, es_filter_cases(domain, filters=filters.filters))

    