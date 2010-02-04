try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import os
import sys
import email
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from django.core.files.uploadhandler import FileUploadHandler, StopFutureHandlers


class LegacyXFormUploadParsingHandler(FileUploadHandler):
    """
    HQ's version of an upload handler that takes the raw_post_data of a text or multipar/mixed blob and populates
    the request.FILES variable.
    
    This is still a little hacky in how it uses the request.FILES, but the gist is is, that it'll split out
    the multipart submission into key/value pairs in the request.FILES.
    
    When you access request.FILES, django will loop through the available upload handlers to see which one returns something
    interesting.  Prior to this, we would try to access the raw_post_data and parse it by hand.  However with trying
    to support a legacy + multipart/form based system, checking the request.FILES would destroy raw_post_data which was
    helpful for our control flow.
    
    This version of the upload handler will attempt to parse the xform blob and put it into the request.FILES, while putting the
    original raw data in parameter raw_post_data.    
    """

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        """
        Takes raw input that is of a legacy j2me submission for CommCare and parse it into the request.FILES
        
        Following the django documentation, the return is a tuple of self.request, querydict<>
        """        
        self.activated = True
        
        files = {}
        body = input_data.read()
        preamble = "Content-type: %s\n" % META['CONTENT_TYPE']
        preamble += "Content-length: %d\n\n" % content_length                        
        parsed_message = email.message_from_string(preamble + body)                
        for part in parsed_message.walk():                                
            try:                 
                if part.get_content_type() == 'multipart/mixed':            
                    logging.debug("Multipart part")                        
                    #this is the main wrapper, this shouldn't ever happen
                else:
                    content_type = part.get_content_type()                    
                    if content_type.startswith('text/') or content_type.startswith('multipart/form-data'):
                        uri = 'legacy_xform'                  
                    else:
                        logging.debug("non XML section: %s" % part['Content-ID'])
                        uri = part['Content-ID']                        
                    
                    filename= os.path.basename(uri)                
                    payload = part.get_payload().strip()                    
                    fstream = StringIO(payload)               
                    
                    files[filename] = InMemoryUploadedFile(
                                                           file = fstream,
                                                           field_name = filename,
                                                           name=filename,
                                                           content_type=content_type,
                                                           size=len(payload),
                                                           charset = None
                                                           )                         
            except Exception, e:                 
                type, value, tb = sys.exc_info()                
                logging.error("Legacy blob handling error")
                return
        if len(files.keys()) == 0:
            return
        else:
            #we've got something and we're going to return the dictionary.
            #for safety's sake, we'll put in the original raw post for the view to save it just like old times
            files['raw_post_data'] = body
            return (self.request, files)        

    def receive_data_chunk(self, raw_data, start):
        """
        Add the data to the StringIO file.
        """
        if self.activated:
            self.file.write(raw_data)
        else:
            return raw_data

    def file_complete(self, file_size):
        """
        Return a file object if we're activated.
        """
        pass
    
    
    
class LegacyXFormUploadBlobHandler(FileUploadHandler):
    """HQ's version of an upload handler that takes the raw_post_data of a text 
       or multipart/mixed blob and populates the request.FILES variable.
    
       This is still a little hacky in how it uses the request.FILES, but the 
       gist is, that it'll split out the multipart submission into key/value 
       pairs in the request.FILES.
    
       When you access request.FILES, django will loop through the available 
       upload handlers to see which one returns something interesting.  Prior 
       to this, we would try to access the raw_post_data and parse it by hand.  
       However with trying to support a legacy + multipart/form based system, 
       checking the request.FILES would destroy raw_post_data which was helpful 
       for our control flow.
    
       This version of the upload handler just turns around the raw input_data 
       and puts it in request.FILES, and does no processing. 
    """

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        """
        Takes raw input that is of a legacy j2me submission for CommCare and parse it into the request.FILES
        
        Following the django documentation, the return is a tuple of self.request, querydict<>
        """        
        self.activated = True
        files = {}             
        rawdata = input_data.read()
        files['raw_post_data'] = InMemoryUploadedFile(
                                                           file = StringIO(rawdata),
                                                           field_name = 'raw_post_data',
                                                           name='raw_post_data',
                                                           content_type=META['CONTENT_TYPE'],
                                                           size=len(rawdata),
                                                           charset = None
                                                           )  
        return (self.request, files)        

    def receive_data_chunk(self, raw_data, start):
        """
        Add the data to the StringIO file.
        """
        if self.activated:
            self.file.write(raw_data)
        else:
            return raw_data

    def file_complete(self, file_size):
        """
        Return a file object if we're activated.
        """
        pass