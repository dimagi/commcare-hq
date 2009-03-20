from django.db import models
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
    form_name = models.CharField(max_length=255, unique=True)
    xmlns = models.CharField(max_length=255, unique=True)
    date_created = models.DateField(auto_now=True)
    element = models.OneToOneField(ElementDefData)
    #group_id = models.ForeignKey(Group)
    #blobs aren't supported in django, so we just store the filename
    xsd_filename = models.CharField(max_length=255)
    
    def __unicode__(self):
        return self.form_name

