from django.conf.urls.defaults import *
# this module is called api_ because importing from "api.resources" 
# conflicts with the builtin python namespace
from xformmanager.api_.resources import *

urlpatterns = patterns('',
   # remember: order urls by most qualified to least
                       
   # Registered xform schemas
   (r'^api/xforms/(?P<formdef_id>\d+)/schema', XFormSchema() ),

   # At some (later) point, we could support requesting metadata schema
   # (r'^api/xforms/(?P<schema_id>\d+)/metadata/schema', XFormMetadataSchema() ),

   # Retrieve meta info (including unique instance data id) for a specific
   # form submitted to a specific schema
   # https://dev.commcarehq.org/api/xforms/metadata
   # ?format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)/metadata', XFormMetadatum() ),

   # Retrieve meta info (including unique instance data id) 
   # for all forms submitted to a specific schema
   # https://dev.commcarehq.org/api/xforms/metadata
   # ?format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<formdef_id>\d+)/metadata', XFormMetadata() ),

   # Retrieve a specific form submitted to a specific schema
   # https://dev.commcarehq.org/api/xforms
   # ?format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)/$', XFormSubmissionData() ),    

   # Retrieve all forms submitted to a specific schema
   # https://dev.commcarehq.org/api/xforms
   # ?format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<formdef_id>\d+)/$', XFormSubmissionsData() ),    

   # List all registered schemas
   (r'^api/xforms/$', XFormSchemata(permitted_methods=('GET','POST')) ),

   # List allowable api calls
   (r'api/$', XFormApi() ),
)

