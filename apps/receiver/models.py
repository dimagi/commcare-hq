from django.db import models
from datetime import datetime
from hq.models import *

from django.utils.translation import ugettext_lazy as _
from django.core import serializers
from random import choice

import uuid
import settings
import email
import logging
import string
import hashlib
import sys
import os
import traceback

class Submission(models.Model):   
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    transaction_uuid = models.CharField(_('Submission Transaction ID'), max_length=36, default=uuid.uuid1())
    #transaction_num = models.IntegerField(_('Submission Integer ID for Phone'),unique=True,null=False)
    
    domain = models.ForeignKey(Domain)
    
    submit_ip = models.IPAddressField(_('Submitting IP Address'))    
    checksum = models.CharField(_('Content MD5 Checksum'),max_length=32)    
    bytes_received = models.IntegerField(_('Bytes Received'))
    raw_header = models.TextField(_('Raw Header'))
    
    #print settings.RAPIDSMS_APPS
    raw_post = models.FilePathField(_('Raw Request Blob File Location'), match='.*\.postdata$', path=settings.RAPIDSMS_APPS['receiver']['xform_submission_path'], max_length=255)    
    
    @property
    def num_attachments(self):
        return Attachment.objects.all().filter(submission=self).count()
    
    @property
    def xform(self):
        '''
        Returns the xform associated with this, defined by being the
        first attachment that has a content type of text/xml.  If no such
        attachments are found this will return nothing.
        '''
        attachments = self.attachments.order_by("id")
        for attachment in attachments:
            if attachment.attachment_content_type == "text/xml":
                return attachment
        return None
        
        
        
    class Meta:
        ordering = ('-submit_time',)
        verbose_name = _("Submission Log")        
        get_latest_by = "submit_time"
        
    def __unicode__(self):
        return "Submission " + unicode(self.submit_time)
    
    def save(self, **kwargs):        
        super(Submission, self).save()
        self.process_attachments()
    
    def delete(self, **kwargs):        
        os.remove(self.raw_post)
        
        attaches = Attachment.objects.all().filter(submission = self)
        if len(attaches) > 0:
            for attach in attaches:
                attach.delete()                        
        super(Submission, self).delete()
        
    
    def process_attachments(self):
        """Process attachments for a given submission blob.
        Will try to use the email parsing library to get all the MIME content from a given submission
        And write to file and make new Attachment entries linked back to this Submission"""
        fin = open(self.raw_post,'rb')
        body = fin.read()        
        fin.close()        
        parsed_message = email.message_from_string(body)   
        for part in parsed_message.walk():
            try:
                #print "CONTENT-TYPE: " + str(part.get_content_type())     
                if part.get_content_type() == 'multipart/mixed':
                    #it's a multipart message, oh yeah
                    logging.debug("Multipart part")
                    #print part['Content-ID']
                    #continue
                else:                   
                    new_attach= Attachment()
                    new_attach.submission = self
                    content_type = part.get_content_type()
                    new_attach.attachment_content_type=content_type
                    if content_type.startswith('text/') or content_type.startswith('multipart/form-data'):
                        new_attach.attachment_uri = 'xform'
                        filename='-xform.xml'
                    else:
                        logging.debug("non XML section: " + part['Content-ID'])
                        new_attach.attachment_uri = part['Content-ID']
                        filename='-%s' % os.path.basename(new_attach.attachment_uri)
               
                    payload = part.get_payload().strip()
                    new_attach.filesize = len(payload)
                    new_attach.checksum = hashlib.md5(payload).hexdigest()
                    fout = open(os.path.join(settings.RAPIDSMS_APPS['receiver']['attachments_path'],self.transaction_uuid + filename),'wb')
                    fout.write(payload)
                    fout.close() 
                    new_attach.filepath = os.path.join(settings.RAPIDSMS_APPS['receiver']['attachments_path'],self.transaction_uuid + filename)
                    new_attach.save()                
                    logging.debug("Attachment Save complete")                    
            except Exception, e:
                logging.error("error parsing attachments") 
                #logging.error("error parsing attachments: Exception: " + str(sys.exc_info()[0]))
                #logging.error("error parsing attachments: Exception: " + str(sys.exc_info()[1]))
                type, value, tb = sys.exc_info()
                logging.error("Attachment Parse Error Traceback:")
                logging.error(type.__name__ +  ":" + str(value))            
                logging.error(string.join(traceback.format_tb(tb),' '))
        
class Backup(models.Model):
    #backup_code = models.CharField(unique=True,max_length=6)
    backup_code = models.IntegerField(unique=True)
    password = models.CharField(_('backup password'), max_length=128)
    submission = models.ForeignKey(Submission)    
    #other fields?
    
    def __new_code(self):
        """Generate and verify that the backup code is unique"""
        nums = '0123456789'
        new_code = int(''.join([choice(nums) for i in range(6)]))
        while Backup.objects.all().filter(backup_code=new_code).count() != 0:
            new_code = int(''.join([choice(nums) for i in range(6)]))
        return new_code
    
    def save(self, **kwargs):
        self.backup_code = self.__new_code()       
        #todo:  process password using similar method from the User model for password salt and hashing
        super(Backup, self).save()
            
    
class Attachment(models.Model):
    submission = models.ForeignKey(Submission, related_name="attachments")
    attachment_content_type = models.CharField(_('Attachment Content-Type'),max_length=64)
    attachment_uri = models.CharField(_('File attachment URI'),max_length=255)
    filepath = models.FilePathField(_('Attachment File'),match='.*\.attach$',path=settings.RAPIDSMS_APPS['receiver']['xform_submission_path'],max_length=255)
    filesize = models.IntegerField(_('Attachment filesize'))
    checksum = models.CharField(_('Attachment MD5 Checksum'),max_length=32)
    
    def get_media_url(self):
        basename = os.path.basename(self.filepath)
        return settings.MEDIA_URL + "attachment/" + basename

    
    def delete(self, **kwargs):       
        os.remove(self.filepath)        
        super(Attachment, self).delete()
    
    def has_duplicate(self):
        '''
        Checks if this has any duplicate submissions, 
        defined by having the same checksum, but a different
        id.
        '''
        return len(Attachment.objects.filter(checksum=self.checksum).exclude(id=self.id)) != 0
        
    def is_duplicate(self):
        '''
        Checks if this is a duplicate submission,
        defined by having other submissions with 
        the same checksum, but a different id, and 
        NOT being the first one
        '''
        all_matching_checksum = Attachment.objects.filter(checksum=self.checksum)
        if len(all_matching_checksum) <= 1:
            return False
        all_matching_checksum = all_matching_checksum.order_by("submission__submit_time").order_by("id")
        return self.id != all_matching_checksum.order_by("submission__submit_time").order_by("id")[0].id
    
    def has_linked_schema(self):
        '''
        Returns whether this submission has a linked schema, defined
        by having something in the xform manager that knows about this.
        '''
        # this method, and the one below are semo-dependant on the 
        # xformmanager app.  if that app is not running, this will
        # never be true but will still resolve.
        if self.get_linked_metadata():
            return True
        return False
    
    def get_linked_metadata(self):
        '''
        Returns the linked metadata for the form, if it exists, otherwise
        returns nothing.
        '''
        if hasattr(self, "form_metadata"):
            try:
                return self.form_metadata.get()
            except:
                return None
        return None
                            
    class Meta:
        ordering = ('-submission',)
        verbose_name = _("Submission Attachment")        
    
    def __unicode__(self):
        return "Attachment %s %s"  % (self.id, self.attachment_uri)
    
