'''
A command linked to a form or domain.  Does some shared handling of 
the form and domain parameters so that subclasses can use it.  For
the help text assumes that the absence of either param is equivalent
to specifying all of them, although subclasses are free to do whatever
they want with the params after they are returned.
'''

import sys
from optparse import make_option

from django.core.management.base import BaseCommand

from django_rest_interface import util as rest_util
from xformmanager.manager import XFormManager
from xformmanager.models import FormDefModel
from domain.models import Domain

class FormCommand(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-d','--domain', action='store', dest='domain_name', \
                    default=None, help='The name of the domain (if any).'),
        make_option('-f','--form', action='store', dest='form_id', \
                    default=None, help='The ID of the form (if any).'),
    )
    
    def get_form_and_domain(self, **options):
        domain_name = options.get("domain_name")
        form_id     = options.get("form_id")
        
        form = None
        domain = None
        
        # get the form
        if form_id:
            try:
                form = FormDefModel.objects.get(id=form_id)
            except FormDefModel.DoesNotExist:
                print ("ERROR. No form with ID %s found. If you'd like to " + \
                       "include all forms or all forms in a domain then leave " + \
                       "this parameter blank") % form_id
                sys.exit()
        
        # get the domain
        if domain_name:
            try:
                domain = Domain.objects.get(name__iexact=domain_name)
                domains = [domain]
            except Domain.DoesNotExist:
                print ("ERROR!  No domain with name '%s' found.  Known domains are: %s. " + \
                       "You can also leave this blank to include all domains.") % \
                       (domain_name, ", ".join(Domain.objects.values_list("name", flat=True)))
                sys.exit()
        
        if form and domain and form.domain != domain:
            print ("Warning! The form you specified (%s) is not in the domain you specified (%s). " +\
                   "Would you like to go ahead with this anyways?") % (form, domain.name)
            rest_util.are_you_sure()

        return [form, domain]