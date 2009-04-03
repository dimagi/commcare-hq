from django.db import models
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
import uuid
import settings
from django.contrib.auth.models import Group, User
from organization.models import *

#import Group

class ElementDefData(models.Model):
    TYPE_CHOICES = (
        ('string', 'string'),
        ('integer', 'integer'),
        ('int', 'int'),
        ('decimal', 'decimal'),
        ('double', 'double'),
        ('float', 'float'),
        ('dateTime', 'dateTime'),
        ('date', 'date'),
        ('time', 'time'),
        ('gYear', 'gYear'),
        ('gMonth', 'gMonth'),
        ('gDay', 'gDay'),
        ('gYearMonth', 'gYearMonth'),
        ('gMonthDay', 'gMonthDay'),
        ('boolean', 'boolean'),
        ('base64Binary', 'base64Binary'),
        ('hexBinary', 'hexBinary'),
        ('anyURI', 'anyURI'),
        ('listItem', 'listItem'),
        ('listItems', 'listItems'),
        ('select1', 'select1'),
        ('select', 'select'),
        ('geopoint', 'geopoint')
    )

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    table_name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    parent = models.ForeignKey("self", null=True)
    # For now, store all allowable values/enum definitions in one table per form
    allowable_values_table = models.CharField(max_length=255, null=True)
    is_attribute = models.BooleanField(default=False)
    is_repeatable = models.BooleanField(default=False)
    #I don't think we fully support this yet
    #restriction = models.CharField(max_length=255)
       
    def __unicode__(self):
        return self.table_name

class FormDefData(models.Model):
    id = models.AutoField(primary_key=True)
    uploaded_by = models.ForeignKey(ExtUser)
        
    submit_time = models.DateTimeField(_('Submission Time'), default = datetime.now())
    submit_ip = models.IPAddressField(_('Submitting IP Address'))
    bytes_received = models.IntegerField(_('Bytes Received'))

    # META fields to be placed here eventually
    
    xsd_file_location = models.FilePathField(_('Raw XSD'), path=settings.XSD_REPOSITORY_PATH, max_length=255)
    #form_name is used as the table name
    form_name = models.CharField(_('Fully qualified form name'),max_length=255, unique=True)
    form_display_name = models.CharField(_('Readable Name'),max_length=128)
    
    target_namespace = models.CharField(max_length=255, unique=True)
    date_created = models.DateField(auto_now=True)
    element = models.OneToOneField(ElementDefData)    
    #group_id = models.ForeignKey(Group)
    #blobs aren't supported in django, so we just store the filename
    
    def __unicode__(self):
        return "XForm " + unicode(self.form_name)
    
    @property
    def get_domain(self):
        return self.uploaded_by.domain


