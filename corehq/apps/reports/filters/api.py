"""
API endpoints for filter options
"""
from django.http import Http404, HttpResponseBadRequest, HttpResponse
from django.views.generic import View

from ..cache import CacheableRequestMixIn


class EmwfOptionsView(CacheableRequestMixIn, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    
    Includes: 
    unknown: t__3,
    admin: t__2,
    demo: t__1,
    output: {
        
    }
    """

    def get(self, request, *args, **kwargs):
        import json
        return HttpResponse(json.dumps({'msg': "Hi Mom!!"}, indent=2))
