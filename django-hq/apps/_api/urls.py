from django.conf.urls.defaults import *
# this module is called _api because importing from "api.xforms" is illegal in python
from _api.xforms import *

urlpatterns = patterns('',
   # List allowable api calls
   (r'^api/$', XFormApi() ),

   # At some (later) point, we should support requesting metadata schema
   # (r'^api/xforms/(?P<schema_id>\d+)/metadata/schema', XFormMetadataSchema() ),

   # Retrieve meta info (including unique instance data id) for all forms submitted from a given schema
   # https://dev.commcarehq.org/api/xforms/metadata?schema-id=<schema-id>&format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<schema_id>\d+)/metadata/', XFormMetadata() ),

   # At some (later) point, we should support requesting metadata schema
   # (r'^xforms/(?P<schema_id>\d+)/schema', XFormSchema() ),

   # Retrieve all forms submitted in the format of one given schema
   # e.g. https://dev.commcarehq.org/api/xforms?schema-id=<schema-id>&format=xml&start-id=<start-id>&end-id=<end-id>
   (r'^api/xforms/(?P<schema_id>\d+)', XFormSubmissionsData() ),    

   # List all registered schemas
   (r'^api/xforms', XFormSchemas() ),    

)

