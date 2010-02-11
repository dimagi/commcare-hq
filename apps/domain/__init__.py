from django.contrib.auth.models import User
from utilities.debug_client import console_msg as cm

# Class containing strings for use in django_granular_permissions for Domain
class Permissions:
    ADMINISTRATOR = "admin"
    
# Monkeypatch a function onto User to tell if user is administrator of selected domain
def _admin_p (self):
    dom = getattr(self, 'selected_domain', None)    
    if dom is not None:
        return self.has_row_perm(dom, Permissions.ADMINISTRATOR)
    else:
        return False
    
User.is_selected_dom_admin = _admin_p 