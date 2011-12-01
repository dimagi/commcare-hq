from __future__ import absolute_import
from django.db.models.signals import post_save
from corehq.apps.domain.models import Domain, CouchDomain

def update_couch_domain(sender, instance, created, **kwargs):
    couch_domain = CouchDomain.view("domain/domains", key=instance.name, 
                                    reduce=False, include_docs=True).one()
    if couch_domain:
        if couch_domain.is_active != instance.is_active:
            couch_domain.is_active = instance.is_active
            couch_domain.save()
    else:
        couch_domain = CouchDomain(name=instance.name, 
                                   is_active=instance.is_active,
                                   is_public=False)
        couch_domain.save()
    
post_save.connect(update_couch_domain, sender=Domain)