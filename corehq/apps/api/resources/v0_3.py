from corehq.apps.cloudcare.api import es_filter_cases
from . import v0_2 
from corehq.apps.api.resources.v0_2 import dict_object
from tastypie import fields

class CaseListFilters(object):
    format = 'json'
    
    def __init__(self, params):
        self.filters = dict((k, v) for k, v in params.items())
        if 'format' in self.filters:
            self.format = self.filters['format']
            del self.filters['format']
        
class CommCareCaseResource(v0_2.CommCareCaseResource):
    
    # in v2 this can't be null, but in v3 it can
    user_id = fields.CharField(attribute='user_id', null=True)
    
    def obj_get_list(self, request, domain, **kwargs):
        filters = CaseListFilters(request.GET)
        return map(dict_object, es_filter_cases(domain, filters=filters.filters))

    