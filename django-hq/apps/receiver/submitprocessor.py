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

def get_submission_path():
    return settings.rapidsms_apps_conf['receiver']['xform_submission_path']                    

@transaction.commit_on_success
def do_raw_submission(metadata, payload, domain=None, is_resubmission=False):
    logging.debug("Begin do_raw_submission()")
    transaction = str(uuid.uuid1())
    new_submit = Submission()
    new_submit.transaction_uuid = transaction
    if is_resubmission:
        new_submit.submit_ip = metadata['HTTP_ORIGINAL_IP']
        new_submit.submit_time = datetime.strptime(metadata['HTTP_TIME_RECEIVED'], "%Y-%m-%d %H:%M:%S")
    else:
        if metadata.has_key('HTTP_X_FORWARDED_FOR'):
            new_submit.submit_ip = metadata['HTTP_X_FORWARDED_FOR']
        elif metadata.has_key('REMOTE_HOST') and len(metadata['REMOTE_HOST'])>0:
            new_submit.submit_ip = metadata['REMOTE_HOST']
        else:
            new_submit.submit_ip = '127.0.0.1'
            
    if metadata.has_key('HTTP_CONTENT_TYPE'):
        content_type = metadata['HTTP_CONTENT_TYPE']
    else:
        content_type = metadata['CONTENT_TYPE']#"text/xml"    
    
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
        newfilename = os.path.join(get_submission_path(),transaction + '.postdata')
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
        
    logging.debug("try to write model")   
    new_submit.domain = domain     
    new_submit.save()
    logging.debug("save to db successful")
    return new_submit