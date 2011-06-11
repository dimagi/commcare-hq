from sofabed.forms.models import FormDataBase
from django.db import models
from corehq.apps.users.models import CouchUser
from couchdbkit.resource import ResourceNotFound
from corehq.apps.users.exceptions import NoAccountException

class HQFormData(FormDataBase):
    """
    HQ's implementation of FormData. In addition to the standard attributes
    we save additional HQ-specific things like the domain of the form, and
    some additional user data.
    """
    
    domain = models.CharField(max_length=200)
    username = models.CharField(max_length=200, blank=True)
    
    def _get_username(self):
        if self.userID:
            try:
                user = CouchUser.get(self.userID)
                return user.raw_username
            except ResourceNotFound:
                pass # no user doc
            except NoAccountException:
                pass # no linked account
        
        return ""
    
    def update(self, instance):
        """
        Override update to bolt on the domain
        """
        super(HQFormData, self).update(instance)
        self.domain = instance.domain or ""
        self.username = self._get_username()
            
    def matches_exact(self, instance):
        return super(HQFormData, self).matches_exact(instance) and \
               self.domain == instance.domain