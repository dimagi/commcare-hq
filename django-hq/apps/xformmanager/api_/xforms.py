from datetime import datetime
from django.core import serializers
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django_rest_interface.resource import Resource
from transformers.csv_ import get_csv_from_django_query
from xformmanager.util import get_csv_from_form
from xformmanager.xformdef import FormDef
from xformmanager.models import *
from organization.models import *

""" changes to the API need to occur in 
* api/urls.py (redirection)
* api/xforms.py (implementation)
* api/templates/api.xml (documentation)
"""

# TODO - come back and clean this up to use more of the django-rest-interface
# goodness (i.e. reduce duplicate 'serialize' calls by using Collections)
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
class XFormSchemata(Resource):
    def read(self, request, template= 'api_/xforms.xml'):
        """ lists all registered schemas """
        try:
            extuser = ExtUser.objects.all().get(id=request.user.id)
        except ExtUser.DoesNotExist:
            return HttpResponseBadRequest("You do not have permission to use this API.")
        xforms = FormDefModel.objects.filter(domain=extuser.domain).order_by('id')
        if not xforms: return HttpResponseBadRequest(\
            "No schemas have been registered for %s." % extuser.domain)
        # using django's lazy queryset evaluation awesomeness
        if request.REQUEST.has_key('start-id'):
            xforms = xforms.filter(pk__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            xforms = xforms.filter(pk__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            xforms = xforms.filter(submit_time__gte=date)
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            xforms = xforms.filter(submit_time__lte=date)
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
            return HttpResponseBadRequest("Schema with primary key %s was not found." % formdef_id)
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

# api/xforms/(?P<schema_id>\d+)
class XFormSubmissionsData(Resource):
    def read(self, request, formdef_id):
        """ list all submitted instance data for a particular schema """
        try:
            formdef = FormDefModel.objects.get(pk=formdef_id)
        except FormDefModel.DoesNotExist:
            return HttpResponseBadRequest("Schema with id %s could not found." % formdef_id)            
        metadata = Metadata.objects.filter(formdefmodel=formdef).order_by('id')
        if not metadata:
            return HttpResponseBadRequest("Metadata of schema with id %s not found." % formdef_id)
        filter = ''
        if request.REQUEST.has_key('start-id'):
            if filter: filter = filter + " AND "
            filter = filter + "id >= " + request.GET['start-id']
        if request.REQUEST.has_key('end-id'):
            if filter: filter = filter + " AND "
            filter = filter + "id <= " + request.GET['end-id']
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            # not the most efficient way of doing this 
            # but it keeps our django orm reference and sql work separate
            metadata = metadata.filter(submission__submission__submit_time__gte=date)
            raw_ids = [m.raw_data for m in metadata]
            if filter: filter = filter + " AND "
            filter = filter + "id IN " + unicode(raw_ids)
            filter = filter.replace('[','(').replace(']',')')
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__lte=date)
            raw_ids = [m.raw_data for m in metadata]
            if filter: filter = filter + " AND "
            filter = filter + "id IN " + unicode(raw_ids)
            filter = filter.replace('[','(').replace(']',')')
        return get_csv_from_form(formdef_id, filter=filter)

# api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)
class XFormSubmissionData(Resource):
    def read(self, request, formdef_id, form_id):
        """ return data from a specific submission """
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                formdef = FormDefModel.objects.get(pk=formdef_id)
                if not formdef: return HttpResponseBadRequest(\
                    "Schema with primary key %s was not found." % formdef_id)
                try:
                    meta = Metadata.objects.get(raw_data=form_id, formdefmodel=formdef)
                except Metadata.DoesNotExist:
                    return HttpResponseBadRequest(\
                        "Instance with id %s and schema %s was not found." % form_id, formdef.id)
                fin = open( meta.xml_file_location() ,"r")
                response = HttpResponse(fin.read(), mimetype='text/xml')
                fin.close()
                return response
            elif request.GET['format'].lower() == 'json': 
                return get_json_from_form(formdef_id, form_id)
        #default to CSV
        return get_csv_from_form(formdef_id, form_id=form_id)        

# api/xforms/(?P<formdef_id>\d+)/metadata/
class XFormMetadata(Resource):
    
    def read(self, request, formdef_id):
        """  lists all metadata associated with all instances submitted 
        to a particular schema
        
        """
        # CSV
        metadata = Metadata.objects.filter(formdefmodel=formdef_id).order_by('id')
        if not metadata:
            return HttpResponseBadRequest("Metadata of schema with id %s not found." % formdef_id)
        if request.REQUEST.has_key('start-id'):
            metadata = metadata.filter(pk__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            metadata = metadata.filter(pk__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__gte=date)
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__lte=date)
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
            return HttpResponseBadRequest(\
                "Metadatum of form (id=%s) with schema (id=%s) not found." % (form_id, formdef_id) )
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                response = HttpResponse(mimetype='text/xml')
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(metadatum, stream=response, fields = \
                    ('formname','formversion','deviceid','timestart','timeend',\
                     'username','chw_id','uid','raw_data') )
                return response
        return get_csv_from_django_query(metadatum)

