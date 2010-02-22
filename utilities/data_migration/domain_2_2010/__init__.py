from django.db import models

class Domain(models.Model):
    '''Domain is the highest level collection of people/stuff
in the system. Pretty much everything happens at the
domain-level, including permission to see data, reports,
charts, etc.'''
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    timezone = models.CharField(max_length=64,null=True)
    
    def get_blacklist(self):
        '''Get the list of names on the active blacklist.'''
        # NOTE: using this as a blacklist check implies a list lookup for each
        # user which could eventually get inefficient. We could make this a
        # hashset if desired to make this O(1)
        return self.blacklisteduser_set.filter(active=True)\
                        .values_list('username', flat=True)
        
        
        
    def __unicode__(self):
        return self.name
 
    class Meta:
        verbose_name = _("Domain Account")