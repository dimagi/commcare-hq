from django.db import models
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
import uuid
import settings


class SubmitLog(models.Model):   
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    transaction_uuid = models.CharField(_('Submission Transaction ID'), max_length=36, default=uuid.uuid1())
    
    submit_ip = models.IPAddressField(_('Submitting IP Address'))    
    checksum = models.CharField(_('Content MD5 Checksum'),max_length=32)    
    bytes_received = models.IntegerField(_('Bytes Received'))
    raw_header = models.TextField(_('Raw Header'))    
    raw_post = models.FilePathField(_('Raw Request Blob'),match='.*\.postdata$', path=settings.XFORM_SUBMISSION_PATH)    
        
    class Meta:
        ordering = ('-submit_time',)
        verbose_name = _("Submission Log")        
        get_latest_by = "submit_time"
        
    def __unicode__(self):
        return "Submission " + unicode(self.submit_time)
    
    
class Attachment(models.Model):
    submission = models.ForeignKey(SubmitLog)
    attachent_uri = models.CharField(_('File attachment URI'),max_length=255)
    filepath = models.FilePathField(_('Attachment File'),match='.*\.attach$',path=settings.XFORM_SUBMISSION_PATH,max_length=255)
    filesize = models.IntegerField(_('Attachment filesize'))
    
    class Meta:
        ordering = ('-submission',)
        verbose_name = _("Submission Attachments")        
    def __unicode__(self):
        return "Attachment " + unicode(self.uri)