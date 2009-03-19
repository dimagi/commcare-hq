from django.db import models
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
import uuid


class SubmitLog(models.Model):   
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    submit_ip = models.IPAddressField(_('Submitting IP Address'))    
    checksum = models.CharField(_('Content Checksum'),max_length=32)
    submit_id = models.CharField(_('Submission Transaction ID'), max_length=36, default=uuid.uuid1())
    bytes_received = models.IntegerField(_('Bytes Received'))
    raw_request = models.TextField(_('Raw Request Time'))    
        
    class Meta:
        ordering = ('-submit_time',)
        verbose_name = _("Submission Log")        
        get_latest_by = "submit_time"
    def __unicode__(self):
        return "Submission " + unicode(self.submit_time)