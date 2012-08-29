from couchdbkit.exceptions import ResourceNotFound
from couchforms.models import XFormInstance
from sofabed.forms.models import FormDataBase
from django.db import models
from sofabed.forms.exceptions import InvalidFormUpdateException
from corehq.apps.users.util import user_id_to_username

class HQFormData(FormDataBase):
    """
    HQ's implementation of FormData. In addition to the standard attributes
    we save additional HQ-specific things like the domain of the form, and
    some additional user data.
    """
    
    domain = models.CharField(max_length=200)
    username = models.CharField(max_length=200, blank=True)
    # todo: uncomment the following
    # app_id = models.CharField(max_length=200, null=True)

    @property
    def app_id(self):
        try:
            return XFormInstance.get(self.instanceID).app_id
        except (ResourceNotFound, AttributeError, KeyError):
            return None

    def _get_username(self):
        if self.userID:
            return user_id_to_username(self.userID) or ""
            
        return ""
    
    def update(self, instance):
        """
        Override update to bolt on the domain
        """
        super(HQFormData, self).update(instance)
        
        if not hasattr(instance, "domain") or not instance.domain:
            # we don't allow these fields to be empty
            raise InvalidFormUpdateException("No domain found in instance %s!" %\
                                             (instance.get_id))
        
        self.domain = instance.domain 
        self.username = self._get_username()
            
    def matches_exact(self, instance):
        return super(HQFormData, self).matches_exact(instance) and \
               self.domain == instance.domain