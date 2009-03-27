from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _

# Create your models here.

class EdgeType(models.Model):
    #inline admin fixes:
    #http://www.thenestedfloat.com/articles/limiting-inline-admin-objects-in-django
    
    directional = models.BooleanField(default=True)    
    
    name = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    
    parent_type = models.ForeignKey(ContentType, related_name='parent_type')
    child_type = models.ForeignKey(ContentType,related_name = 'child_type')    

    class Meta:
        #verbose_name = _("Edge Type")
        #abstract=True  
        pass      
    
    def __unicode__(self):
        if self.directional:
            direction = " ==> "
        else:
            direction = " <--> "
        
        return " Edge Type: %s [%s %s %s] %s" % (self.name,self.parent_type,direction,self.child_type,self.description)


class Edge(models.Model):    
    relationship = models.ForeignKey(EdgeType)
    
    parent_type = models.ForeignKey(ContentType, verbose_name=_('parent content type'),related_name='parent_type_set')
    parent_id    = models.PositiveIntegerField(_('parent object id'), db_index=True)
    parent_object = generic.GenericForeignKey(ct_field='parent_type', fk_field='parent_id')
        
    child_type = models.ForeignKey(ContentType, verbose_name=_('child content type'),related_name='child_type_set')
    child_id    = models.PositiveIntegerField(_('child object id'), db_index=True)
    child_object = generic.GenericForeignKey(ct_field='child_type',fk_field='child_id')    
        
    class Meta:
#    verbose_name = _("Edge")
#    abstract=True
        pass
   
    def __unicode__(self):
        return "(" + unicode(self.parent_object) + unicode(self.relationship) + unicode(self.child_object) + ")" 
    
    def save(self):
        #todo, we need to fracking make sure that a few conditions exist:
        # that it's no dupe
        # no cycles!
        super(Edge, self).save()
        pass
    
    def _get_allowable_objects(self):
        pass