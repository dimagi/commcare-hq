# Use modern Python
from __future__ import unicode_literals, print_function, absolute_import

# Standard Library imports

# Django imports
from django.conf import settings
import django.core.exceptions

# External imports
from redis_cache.exceptions import ConnectionInterrumped
from dimagi.utils.couch.cache import cache_core
import toggle.shortcuts
from django_prbac.models import Role

# CCHQ imports
from corehq import toggles

class CCHQPRBACMiddleware(object):
    """
    MiddleWare to add request.role based on user or domain
    information. This _must_ be placed after the
    UserMiddleWare if you want it to find the domain and user
    on the request object.

    Note that because the domain comes from the view kwargs, these are all
    'process_view' middleware classes.

    Also note that this is, for now, used only for domain/plan privileges
    so request.role is the Role for the domain's plan, not for the user.
    Neither domains nor users currently have roles in the PRBAC tables.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):

        # Until we have real roles, we can demo for certain users by just letting them specify
        # on the querystring
        if hasattr(request, 'user') and toggle.shortcuts.toggle_enabled(toggles.PRBAC_DEMO, request.user.username):
            role_slug = request.GET.get('role', 'community_plan_v0')
            request.role = Role.objects.get(slug=role_slug)
            return None

        if hasattr(request, 'domain'):
            # TODO once accounting is merged: role = accounting.role_for_domain(domain)
            request.role = Role()
        else:
            request.role = Role() # A fresh Role() has no privileges

        return None
    
############################################################################################################
