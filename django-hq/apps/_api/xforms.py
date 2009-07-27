from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from _api.rest_api.resource import Resource
import settings, os
from xformmanager.models import *
from organization.models import *

# Urls for a resource that does not map 1:1 to Django models.

""" changes to the API need to occur in 
* api/urls.py (redirection)
* api/xforms.py (implementation)
* api/templates/api.xml (documentation)
"""


"""
supported formats:
*http?
*xml
*csv
*json?
"""

# TODO - pull out authentication stuff into some generic wrapper
#if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponse("You do not have permissions to use this API. Please login.")

# api/ - list all api calls
class XFormApi(Resource):
    def read(self, request, template='api.xml'):
        # put all the api calls in context, then select html, xml, csv, json as needed
        context = {}
        return render_to_response(template, context, context_instance=RequestContext(request) )

# api/xforms - list all registered schemas
class XFormSchemas(Resource):
    def read(self, request, template='xforms.xml'):
        # put all the api calls in context, then select html, xml, csv, json as needed
        context = {}
        extuser = ExtUser.objects.all().get(id=request.user.id)
        context['available_form_ids'] = FormDefModel.objects.filter(domain= extuser.domain).values_list('id', flat=True).order_by('id')
        return render_to_response(template, context, context_instance=RequestContext(request) )

# api/xforms/(?P<schema_id>\d+) - list all submitted instance data for a particular schema
class XFormSubmissionsData(Resource):
    def read(self, request, schema_id):
        if request.REQUEST.has_key('start_id'):
            request.GET['start_id']
        if request.REQUEST.has_key('start_date'):
            request.GET['start_date']
        if request.REQUEST.has_key('format'):
            request.GET['format']
        
        # TODO: use 'transformers' api to generically generate different data formats
        # the following junk should disappear

        # XML
        # run transformers.generate_XML on raw data

        # CSV
        form_name = (FormDefModel.objects.get(id=schema_id)).form_name
        # once the metadata table is working, modify this to point to the database file location
        if os.path.exists( os.path.join( settings.RAPIDSMS_APPS['xformmanager']['csv_path'] ,form_name + ".csv" ) ):
            f = open(  os.path.join( settings.RAPIDSMS_APPS['xformmanager']['csv_path'] ,form_name+".csv") , "r" )
            return HttpResponse(f.read(), mimetype='application/ms-excel')
        return HttpResponse("No CSV data available for form " + form_name)

        # HTTP?
        # run transformers.generate_HTTP on raw data?

        # JSON
        # run generate_JSON on raw tables

#api/xforms/(?P<schema_id>\d+)/metadata/ - list all metadata associated with all instances submitted to a particular schema
class XFormMetadata(Resource):
    def read(self, request, schema_id, template='xformmetadata.xml'):
        # TODO: use 'transformers' api to generically generate different data formats
        # the following junk should disappear
        context = {}
        context['metadata'] = Metadata.objects.filter(formdefmodel=schema_id).order_by('id')
        return render_to_response(template, context, context_instance=RequestContext(request) )


