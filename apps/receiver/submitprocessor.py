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
from receiver.models import _XFORM_URI

def get_submission_path():
    return settings.RAPIDSMS_APPS['receiver']['xform_submission_path']
def save_legacy_blob(submission, rawpayload):
    '''
       Saves a legacy raw formed blob POST to a file.  Assumes the body of the post is
       in the raw_post_data of thre request, and the metadata is a hash of the headers.
       If the content-length is not present it will assume the size
       of the payload is the content length. 
       If the content-type is not present it will assume "text/xml".
       
        No return value.  This is just a separate function to save the legacy blob to the filesystem
    '''    
    submit_guid = submission.transaction_uuid    
    try:
        newfilename = os.path.join(get_submission_path(), submit_guid + '.postdata')
        logging.debug("Begin write of legacy blob file")
        fout = open(newfilename, 'wb')
        fout.write('Content-type: %s\n' % submission.content_type.replace("'newdivider'","newdivider"))
        fout.write('Content-length: %s\n\n' % submission.bytes_received)                
        fout.write(rawpayload)
        fout.close()
                
        #file write successful, let's update update the submission with the new checksum
        submission.raw_post = newfilename        
        submission.save()
                
        logging.debug("Legacy blob write successful")            
    except:
        logging.error("Unable to write raw post data: Exception " + str(sys.exc_info()[0]) + " Traceback: " + str(sys.exc_info()[1]))
        # these are HARD errors.  Don't swallow them.
        raise
    
@transaction.commit_on_success
def new_submission(metadata, checksum, domain=None, is_resubmission=False):
    '''Saves the actual db models for the submission and attachment objects.
       Should be called after calling the save_raw_post_file method on a submission.
       Any post-save hooks are probably called from this method as well.
       
       Arguments:
       metadata = request metadata dictionary
       checksum = checksum value to be set with the primary content.
       domain = domain doing the submission
       is_resubmission = if the submission is being resubmitted from the filesystem
       '''
    new_submit = Submission()
    new_submit.transaction_uuid = str(uuid.uuid1())
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
    
    #dmyung - split up the ip address field if it's been appended.  something we ran into depending on some gateways
    #from our understanding the rightmost should be the originating/external IP    
    if len(new_submit.submit_ip.split(',')) > 1:
        new_submit.submit_ip = new_submit.submit_ip.split(',')[-1]
        
    if metadata.has_key('HTTP_CONTENT_TYPE'):
        new_submit.content_type = metadata['HTTP_CONTENT_TYPE']
    elif metadata.has_key('CONTENT_TYPE'):
        new_submit.content_type = metadata['CONTENT_TYPE']
    else:
        new_submit.content_type = "text/xml"    
    
    if metadata.has_key('HTTP_CONTENT_LENGTH'):
        new_submit.bytes_received = int(metadata['HTTP_CONTENT_LENGTH'])
    elif metadata.has_key('CONTENT_LENGTH'):        
        new_submit.bytes_received = int(metadata['CONTENT_LENGTH'])        
    
    new_submit.raw_header = repr(metadata)    
    new_submit.domain = domain
    new_submit.checksum = checksum
    
    new_submit.save()
    logging.debug("Raw submission save successful")
    return new_submit
 
 
 
def new_attachment(submission, payload, content_type, attach_uri, outfilename, *args, **kwargs):
    """Simple wrapper method to save an attachment.
    This probably should be an override of the constructor for attachment"""
    new_attach = Attachment()
    new_attach.submission = submission    
    new_attach.filesize = len(payload)
    new_attach.checksum = hashlib.md5(payload).hexdigest()    
    new_attach.attachment_content_type = content_type    
    new_attach.attachment_uri = attach_uri
    
    fout = open(os.path.join(settings.RAPIDSMS_APPS['receiver']['attachments_path'], outfilename),'wb')
    fout.write(payload)
    fout.close() 
    
    new_attach.filepath = os.path.join(settings.RAPIDSMS_APPS['receiver']['attachments_path'], outfilename)
    new_attach.save()
    
    return new_attach 
 
@transaction.commit_on_success
def handle_legacy_blob(submission): 
    """
    Process attachments for a given submission blob.
    Will try to use the email parsing library to get all the MIME content from a given submission
    And write to file and make new Attachment entries linked back to this Submission"""
    
    # only process attachments on newly created instances, not all of them
    parts_dict = {}    
    
    if submission.raw_post == None:
        logging.error("Attempting to parse a legacy submission but no legacy blob exists in the filesystem!")
        raise
    
    fin = open(submission.raw_post,'rb')
    body = fin.read()        
    fin.close()        
    parsed_message = email.message_from_string(body)    
       
    for part in parsed_message.walk():
        try:                 
            if part.get_content_type() == 'multipart/mixed':            
                logging.debug("Multipart part")                
            else:
                content_type = part.get_content_type()                
                # data submitted from the webui is always 'multipart'
                if content_type.startswith('text/') or content_type.startswith('multipart/form-data'):
                    uri = _XFORM_URI
                    filename = submission.transaction_uuid + '-xform.xml'
                else:
                    logging.debug("non XML section: %s" % part['Content-ID'])
                    uri = part['Content-ID']
                    #the URIs in the j2me submissions are local file URIs to the phone.  we will get the filename from the end of the string
                    filename='%s-%s' % (submission.transaction_uuid, os.path.basename(uri))
                      
                payload = part.get_payload().strip()
                attachment = new_attachment(submission, payload, content_type, uri, filename)
                parts_dict[uri] = attachment
                logging.debug("Attachment Save complete")                    
        except Exception, e:                 
            type, value, tb = sys.exc_info()            
            logging.error("Attachment Parsing Error!!! Traceback: " + type.__name__ +  ":" + str(value) + " " + string.join(traceback.format_tb(tb),' '))
            return {}
    return parts_dict



@transaction.commit_on_success
def handle_multipart_form(submission, request_files):
    """This is a method for processing the multipart/form-data that ODK submits its data.
    Eventually HQ should receive this information as the default way to transport the xforms, as it is more intuitive
    to the server and the developer alike.
    """
    parts_dict = {}    
    try:
        #special case, we parse out the xform first and foremost
        xformobj = request_files['xml_submission_file']    
        xform_filename = submission.transaction_uuid + '-xform.xml'    
        parts_dict['xform'] = new_attachment(submission, xformobj.read(), xformobj.content_type, 'xform', xform_filename)
    except Exception, e:
        logging.debug("Catching any duplicate saving errors")        
            
    #next, pop out the xform we just parsed out, and walk through other attachments if need be and do the same
    otherfiles = request_files.keys()    
    otherfiles.remove('xml_submission_file')
    for fkey in otherfiles:
        try:
            f = request_files[fkey]
            part_filename = submission.transaction_uuid + '-' + f.name    
            parts_dict[f.name] = new_attachment(submission, f.read(), f.content_type, f.name, part_filename)    
        except Exception, e:
            logging.debug("Catching any other attachment issues")

    return parts_dict    


