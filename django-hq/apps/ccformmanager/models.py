from django.db import models
#import Group

class ElementDef(models.Model):
  DATA_TYPE_CHOICES = (
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

  table_name = models.CharField(max_length=512, unique=True)
  is_repeatable = models.BooleanField(default=False)
  binding = models.CharField(max_length=512)
  datatype = models.CharField(max_length=12, choices=DATA_TYPE_CHOICES)
  is_attribute = models.BooleanField(default=False)
  parent_id = models.ForeignKey("self", null=True)
  # For now, store all allowable values/enum definitions in one table per form
  allowable_values_table = models.CharField(max_length=512)
   
  def __unicode__(self):
    return self.name

class FormDef(models.Model):
  form_name = models.CharField(max_length=511, unique=True)
  date_created = models.DateField()
  element_id = models.OneToOneField(ElementDef)
  #group_id = models.ForeignKey(Group)
  #blobs aren't supported in django, so we just store the filename
  xsd_filename = models.CharField(max_length=256)

  def __unicode__(self):
    return self.name