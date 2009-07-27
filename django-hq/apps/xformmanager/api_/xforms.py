from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django_rest_interface.resource import Resource
from transformers.csv_ import get_csv_from_django_query
from xformmanager.util import get_csv_from_form
from xformmanager.xformdef import FormDef
from xformmanager.models import *
from organization.models import *
from django.core import serializers

""" changes to the API need to occur in 
* api/urls.py (redirection)
* api/xforms.py (implementation)
* api/templates/api.xml (documentation)
"""

# TODO - come back and clean this up to use more of the django-rest-interface
# goodness (i.e. reduce duplicate 'serialize' calls
# TODO - pull out authentication stuff into some generic wrapper
# if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponse("You do not have permissions to use this API.")

# api/
class XFormApi(Resource):
    def read(self, request, template='api.xml'):
        """ lists all api calls """
        context = {}
        return render_to_response(template, context, context_instance=RequestContext(request) )

# api/xforms
class XForms(Resource):
    def read(self, request, template= 'api_/xforms.xml'):
        """ lists all registered schemas """
        extuser = ExtUser.objects.all().get(id=request.user.id)
        xforms = FormDefModel.objects.filter(domain=extuser.domain).order_by('id')
        if not xforms: return HttpResponseBadRequest("No schemas have been registered.")
        response = HttpResponse()
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'json':
                json_serializer = serializers.get_serializer("json")()
                json_serializer.serialize(xforms, ensure_ascii=False, stream=response, fields = \
                    ('form_name','form_display_name','target_namespace','submit_time'))
                response['mimetype'] = 'application/ms-excel'
                return response
            elif request.GET['format'].lower() == 'xml': 
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(xforms, stream=response, fields = \
                    ('form_name','form_display_name','target_namespace','submit_time'))
                response['mimetype'] = 'text/xml'
                return response
        # default to CSV
        return get_csv_from_django_query(xforms)

# api/xforms/(?P<schema_id>\d+)
class XFormSubmissionsData(Resource):
    def read(self, request, formdef_id):
        """ list all submitted instance data for a particular schema """
        return get_csv_from_form(formdef_id)

# api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)
class XFormSubmissionData(Resource):
    def read(self, request, formdef_id, form_id):
        """ return data from a specific submission """
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                formdef = FormDefModel.objects.get(pk=formdef_id)
                if not formdef: return HttpResponseBadRequest("Schema not found.")
                try:
                    meta = Metadata.objects.get(raw_data=form_id, formdefmodel=formdef)
                except Metadata.DoesNotExist:
                    return HttpResponseBadRequest("Instance not found.")
                fin = open( meta.xml_file_location() ,"r")
                response = HttpResponse(fin.read(), mimetype='text/xml')
                fin.close()
                return response
            elif request.GET['format'].lower() == 'json': 
                return get_json_from_form(formdef_id, form_id)
        #default to CSV
        return get_csv_from_form(formdef_id, form_id)        

# api/xforms/(?P<formdef_id>\d+)/schema 
class XFormSchema(Resource):
    def read(self, request, formdef_id):
        """ returns the schema for the given form """
        # currently we only support text and xml
        # to support json and csv, we need to query formdef+elementdef recursively
        # note that to do this, we need to build out functionality in storageutility
        # to actually make an element def for each element
        try:
            xsd = FormDefModel.objects.get(pk=formdef_id )
        except FormDefModel.DoesNotExist:
            return HttpResponseBadRequest("Schema not found.")
        fin = open( xsd.xsd_file_location ,"r")
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'text': 
                formdef = unicode( FormDef(fin) )
                response = HttpResponse(formdef, mimetype='text/plain')
                fin.close()
                return response    
        # default to XML                    
        response = HttpResponse(fin.read(), mimetype='text/xml')
        fin.close()
        return response

# api/xforms/(?P<formdef_id>\d+)/metadata/
class XFormMetadata(Resource):
    
    def read(self, request, formdef_id):
        """  lists all metadata associated with all instances submitted 
        to a particular schema
        
        """
        # CSV
        metadata = Metadata.objects.filter(formdefmodel=formdef_id).order_by('id')
        if not metadata:
            return HttpResponseBadRequest("Metadata not found.")
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                response = HttpResponse(mimetype='text/xml')
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(metadata, stream=response, fields = \
                    ('formname','formversion','deviceid','timestart','timeend',\
                     'username','chw_id','uid','raw_data') )
                return response
        return get_csv_from_django_query(metadata)

# api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)/metadata/ 
class XFormMetadatum(Resource):
    def read(self, request, formdef_id, form_id):
        """ lists metadata associated with a partiocular instance """
        # CSV
        metadatum = Metadata.objects.filter(formdefmodel=formdef_id, raw_data=form_id)
        if not metadatum:
            return HttpResponseBadRequest("Metadatum not found.")
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                response = HttpResponse(mimetype='text/xml')
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(metadatum, stream=response, fields = \
                    ('formname','formversion','deviceid','timestart','timeend',\
                     'username','chw_id','uid','raw_data') )
                return response
        return get_csv_from_django_query(metadatum)

