"""
This is a migration script that fake reposts every form registered on the 
server, one at a time.  Useful if you have remapped your xform processing
logic and need to migrate all your forms to the new logic in place.
"""

from xformmanager.management.commands.form_command import FormCommand
from xformmanager.manager import XFormManager
from xformmanager.models import FormDefModel

class Command(FormCommand):
    
    def handle(self, *app_labels, **options):
        form, domain = self.get_form_and_domain(**options)
        manager = XFormManager()
        
        if form:
            print "Migrating Single form: %s." % form
            manager.repost_schema(form)
            return

        if domain:
            forms = FormDefModel.objects.filter(domain=domain)
        else:
            print "Migrating ALL forms."
            forms = FormDefModel.objects.order_by("domain__name").all()
            
        if not forms:
            print "Whoops. Nothing to migrate. Are you sure you registered forms here?"
            return
        
        current_domain = forms[0].domain
        print "Migrating forms in %s" % current_domain
        for form in forms:
            if form.domain != current_domain:
                current_domain = form.domain
                print "Migrating forms in %s" % current_domain
            print "Migrating %s" % form
            manager.repost_schema(form)
