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
from submitrecord import SubmitRecord

def get_submission_path():
    return settings.RAPIDSMS_APPS['receiver']['xform_submission_path']                    


def save_post(metadata, payload):
    '''
       Saves a post to a file.  Assumes the body of the post is
       in the payload, and the metadata is a hash of the headers.
       If the content-length is not present it will assume the size
       of the payload is the content length. 
       If the content-type is not present it will assume "text/xml".
       Returns a filled out SubmitRecord object containing the following fields
            content_type - content type of the submission
            content_length - content length of the submission
            guid - server generated guid
            checksum - md5 has of the submitted data
            file_name - saved file name
            
            
    '''
    
    if metadata.has_key('HTTP_CONTENT_TYPE'):
        content_type = metadata['HTTP_CONTENT_TYPE']
    elif metadata.has_key('CONTENT_TYPE'):
        content_type = metadata['CONTENT_TYPE']
    else:
        content_type = "text/xml"    
    
    if metadata.has_key('HTTP_CONTENT_LENGTH'):
        content_length = int(metadata['HTTP_CONTENT_LENGTH'])
    elif metadata.has_key('CONTENT_LENGTH'):        
        content_length = int(metadata['CONTENT_LENGTH'])
    else:        
        content_length = len(payload)

    submit_guid = str(uuid.uuid1())
    checksum = hashlib.md5(payload).hexdigest()
    try:
        newfilename = os.path.join(get_submission_path(), submit_guid + '.postdata')
        logging.debug("try to write file")
        fout = open(newfilename, 'w')
        fout.write('Content-type: %s\n' % content_type.replace("'newdivider'","newdivider"))
        fout.write('Content-length: %s\n\n' % content_length)                
        fout.write(payload)
        fout.close()
        logging.debug("write successful")
        return SubmitRecord(content_type=content_type,
                            content_length=content_length,
                            guid=submit_guid,
                            checksum=checksum, 
                            file_name=newfilename)
    except:
        logging.error("Unable to write raw post data: Exception " + str(sys.exc_info()[0]) + " Traceback: " + str(sys.exc_info()[1]))
        # these are HARD errors.  Don't swallow them.
        raise 
    
def do_old_submission(metadata, payload, domain=None, is_resubmission=False):
    '''Deprecated method to wrap save_post and do_submission_processing to behave
       like the old API.  This is to keep unit tests happy.  The tests should
       be fixed and this method removed.  It's better for both steps to 
       be done and checked by the caller independently.'''
    submit_record = save_post(metadata, payload)
    return do_submission_processing(metadata, submit_record, domain, is_resubmission)

@transaction.commit_on_success
def do_submission_processing(metadata, submit_record, domain=None, is_resubmission=False):
    '''Saves the actual db models for the submission and attachment objects.
       Should be called after calling the save_post method on a submission.
       Any post-save hooks are probably called from this method as well.'''
       
    logging.debug("Begin do_raw_submission()")
    new_submit = Submission()
    new_submit.transaction_uuid = submit_record.guid
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
            
    new_submit.raw_header = repr(metadata)    
    new_submit.bytes_received = submit_record.content_length
    new_submit.content_type = submit_record.content_type
    new_submit.raw_post = submit_record.file_name
    new_submit.domain = domain
    new_submit.save()
    logging.debug("Raw submission save successful")
    return new_submit
