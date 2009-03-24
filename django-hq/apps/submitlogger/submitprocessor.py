from models import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string
import uuid
from django.db import transaction

@transaction.commit_on_success
def do_raw_submission(metadata, payload):
    logging.debug("Begin do_raw_submission()")
    transaction = str(uuid.uuid1())
    new_submit = SubmitLog()
    new_submit.transaction_uuid = transaction
    logging.debug("Get remote addr")    
    if metadata.has_key('HTTP_X_FORWARDED_FOR'):
        new_submit.submit_ip = metadata['HTTP_X_FORWARDED_FOR']
    else:
        new_submit.submit_ip = metadata['REMOTE_HOST']
    
    if metadata.has_key('HTTP_CONTENT_TYPE'):
        content_type = metadata['HTTP_CONTENT_TYPE']
    else:
        content_type = metadata['CONTENT_TYPE']    
    
    new_submit.raw_header = repr(metadata)
    logging.debug("compute checksum")
    new_submit.checksum = hashlib.md5(payload).hexdigest()
    logging.debug("Get bytes")
    #new_submit.bytes_received = int(request.META['HTTP_CONTENT_LENGTH'])
    if metadata.has_key('HTTP_CONTENT_LENGTH'):
        new_submit.bytes_received = int(metadata['HTTP_CONTENT_LENGTH'])
    else:        
        new_submit.bytes_received = int(metadata['CONTENT_LENGTH'])
    try:            
        newfilename = os.path.join(settings.XFORM_SUBMISSION_PATH,transaction + '.postdata')
        logging.debug("try to write file")
        fout = open(newfilename, 'w')
        fout.write('Content-type: %s\n' % content_type.replace("'newdivider'","newdivider"))
        fout.write('Content-length: %s\n\n' % new_submit.bytes_received)                
        fout.write(payload)
        fout.close()
        logging.debug("write successful")
        new_submit.raw_post = newfilename
    except:
        logging.error("Unable to write raw post data")
        logging.error("Unable to write raw post data: Exception: " + str(sys.exc_info()[0]))
        logging.error("Unable to write raw post data: Traceback: " + str(sys.exc_info()[1]))        
        return '[error]'
        #return render_to_response(template_name, context, context_instance=RequestContext(request))        
        
    logging.debug("try to write model")        
    new_submit.save()
    logging.debug("save to db successful")
    return transaction