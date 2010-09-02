from lxml import etree
from django.http import HttpResponse


# standard xml tags for the OR-compliant forms
OPENROSA_RESPONSE_TAG = "OpenRosaResponse"
OPENROSA_STATUS_CODE = "OpenRosaStatusCode"
OPENROSA_STATUS = "OpenRosaStatus"
STATUS_CODE_TAG = "SubmissionStatusCode"
SUBMIT_ID = "SubmissionId"
FORMS_SENT_TODAY = "FormsSubmittedToday"
TOTAL_FORMS_SENT = "TotalFormsSubmitted"

class SubmitResponse(object):
    '''A simple class for holding some information about how a submission
       was handled and how to respond.  For how this is used in conjunction
       with JavaRosa, see: 
          http://code.dimagi.com/JavaRosa/wiki/ServerResponseFormat
    '''
    
    
    
    def __init__(self, status_code, or_status_code=None, or_status=None, 
                 submit_id=None, forms_sent_today=None, 
                 total_forms_sent=None, **kwargs):
        '''Create an instance of a submission response object.  The only
           required field is the status code, the rest are optional.  Any
           keyword arguments passed in will be included in the response, 
           however if a keyword conflicts with an explicit key above, that
           will be overridden.
        '''
        self._all_params = {}
        self.status_code = status_code
        self.add_param(STATUS_CODE_TAG, status_code)
        self.add_param(OPENROSA_STATUS_CODE, or_status_code)
        self.add_param(OPENROSA_STATUS, or_status)
        self.add_param(SUBMIT_ID, submit_id)
        self.add_param(FORMS_SENT_TODAY, forms_sent_today)
        self.add_param(TOTAL_FORMS_SENT, total_forms_sent)
        for key, value in kwargs.items():
            self.add_param(key, value)
        
    
    def add_param(self, key, value):
        '''Adds a parameter to the response, as a key, value pair.
           If the value is None it does nothing.  This will override
           any previously set parameter.'''
        if value != None:
            self._all_params[key] = value
    
    def to_response(self):
        '''Gets this object as a django HTTP response'''
        return HttpResponse(content=str(self), status=self.status_code, 
                            content_type="text/xml")
        
    
    def __unicode__(self):
        '''Gets this as an xml string, in compliance with:
           http://code.dimagi.com/JavaRosa/wiki/ServerResponseFormat
        '''
        root = etree.Element(OPENROSA_RESPONSE_TAG)
        keys = self._all_params.keys()
        keys.sort()
        for key in keys:
            etree.SubElement(root, key).text=str(self._all_params[key])
        return etree.tostring(root, xml_declaration=True,
                              pretty_print=True, encoding="UTF-8")
        

    def __str__(self):
        return unicode(self).encode('utf-8')