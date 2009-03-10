from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _

# Create your models here.

class EdgeType(models.Model):
    directional = models.BooleanField(default=True)
    name = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _("Edge Type")
    
    def __unicode__(self):
        if self.directional:
            return " << " + self.name + " << "
        else:
            return " - " + self.name + " - "

class Edge(models.Model):
    relationship = models.ForeignKey(EdgeType)
    
    parent_type = models.ForeignKey(ContentType, verbose_name=_('parent content type'),related_name='parent_type_set')
    parent_id    = models.PositiveIntegerField(_('parent object id'), db_index=True)
    parent_object = generic.GenericForeignKey('parent_type', 'parent_id')
        
    child_type = models.ForeignKey(ContentType, verbose_name=_('child content type'),related_name='child_type_set')
    child_id    = models.PositiveIntegerField(_('child object id'), db_index=True)
    child_object = generic.GenericForeignKey('child_type', 'child_id')    
    
    class Meta:
        verbose_name = _("Edge")
   
    def __unicode__(self):
        return "(" + unicode(self.parent_object) + unicode(self.relationship) + unicode(self.child_object) + ")" 
    
    def save(self):
        #todo, we need to fracking make sure that a few conditions exist:
        # that it's no dupe
        # no cycles!
        super(Edge, self).save()
        pass