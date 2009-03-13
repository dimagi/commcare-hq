from django.db import models
#from ccformdef.models import Group

class ElementDef(models.Model):
  DATA_TYPE_CHOICES = ()
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

  #def __init__(self, *args, **kwargs):
  #  self.fields['language'].choices = [enum.name for enum in Enum.objects.all()]
  
  name = models.CharField(max_length=512)
  is_repeatable = models.BooleanField(default=False)
  binding = models.CharField(max_length=512)
  datatype = models.CharField(max_length=12, choices=DATA_TYPE_CHOICES)
  is_attribute = models.BooleanField(default=False)
  parent_id = models.ForeignKey("self", null=True)
  #allowable_values = models.CharField(max_length=512, choices=())  
   
  def __unicode__(self):
    return self.name

class FormDef(models.Model):
  name = models.CharField(max_length=511)
  date_created = models.DateField()
  element_id = OneToOneField(ElementDef)
  #group_id = models.ForeignKey(Group)
    
  def __unicode__(self):
    return self.name