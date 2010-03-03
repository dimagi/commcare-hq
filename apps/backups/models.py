from django.db import models


from domain.models import Domain
from receiver.models import Attachment
import xformmanager.xmlrouter as xmlrouter
from backups.processor import create_backup, BACKUP_XMLNS

class BackupUser(models.Model):
    """Someone who backs things up.  They have a string identifier 
       and a domain."""
    # Note: really these should be CHWs but until we have a working
    # registration workflow we'll just make them these arbitrary 
    # things
    domain = models.ForeignKey(Domain, related_name="backup_users")
    username = models.CharField(max_length=32)
    
    def __unicode__(self):
        return self.username


class Backup(models.Model):
    """An instance of a commcare backup.  Points to a specific device
       as well as a set of users.  Additionally, has information about
       the original attachment that created the backup"""
    attachment = models.ForeignKey(Attachment)    
    device_id = models.CharField(max_length="32")
    users = models.ManyToManyField(BackupUser, null=True, blank=True)
    
    def __unicode__(self):
        return "Id: %s, Device: %s, Users: %s" % (self.id, self.device_id,
                                                  self.users.count())
    
# register our backup method, like a signal, in the models file
# to make sure this always gets bootstrapped.
xmlrouter.register(BACKUP_XMLNS, create_backup)
