from django.db import models
from datetime import datetime



class MonitorIdentity(models.Model):    
    id_name= models.CharField(max_length=32,unique=True)    
    date_registered = models.DateTimeField(default = datetime.now())
    #last_activity = models.DateTimeField(default = datetime.now())
    active = models.BooleanField(default=False)    
    
    class Meta:
        #ordering = ['sitecode']
        pass
    def __unicode__(self):
        return self.id_name

class Hardware(models.Model):
    name = models.CharField(max_length=64, unique=True)
    identifier = models.CharField(max_length=244,unique=True,null=True,blank=True)
    
    
class MonitorDevice(models.Model):
    identity = models.ManyToManyField(MonitorIdentity)
    phone = models.CharField(max_length=30, unique=True, blank=True, help_text="e.g., +251912555555")
    incoming_messages = models.PositiveIntegerField(help_text="The number of messages that uniSMS has received from this Monitor",default=0)
    date_registered = models.DateTimeField(default = datetime.now())
    #last_activity = models.DateTimeField(default = datetime.now())
    #identity = models.ForeignKey(Identity, blank=True,null=True)
    active = models.BooleanField(default=False)       
    
    def __unicode__(self):
        return self.phone    


#http://www.eflorenzano.com/blog/post/secrets-django-orm/
#group functions baby!
class MonitorGroup(models.Model):
    name = models.CharField(max_length=64,unique=True)
    description = models.CharField(max_length=255)
    members = models.ManyToManyField(MonitorIdentity)
    def __unicode__(self):
        return self.name
