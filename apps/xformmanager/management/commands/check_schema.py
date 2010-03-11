"""
Checks a schema or set of schemas for some common known classes of error.
"""
   
from xformmanager.management.commands.form_command import FormCommand
from xformmanager.manager import XFormManager
from xformmanager.models import FormDefModel

class Command(FormCommand):

# TODO
#    option_list = FormCommand.option_list + (
#        make_option('-o','--output_file', action='store', dest='output_file', \
#                    default=None, help='The name of the output file for saving.'),
#    )

    def handle(self, *app_labels, **options):
        form, domain = self.get_form_and_domain(**options)
        
        manager = XFormManager()
        if form:
            print "Checking form %s" % form
            errors, warnings = manager.check_schema(form)
            self.display(form, errors, warnings)
            return
        
        if domain:
            forms = FormDefModel.objects.filter(domain=domain)
        else:
            forms = FormDefModel.objects.order_by("domain__name").all()

        current_domain = forms[0].domain
        print "Checking forms in %s" % current_domain
        for form in forms:
            if form.domain != current_domain:
                current_domain = form.domain
                print "Checking forms in %s" % current_domain
            errors, warnings = manager.check_schema(form)
            self.display(form, errors, warnings)

                
    def display(self, form, errors, warnings):
        if errors:
            print "Found the following ERRORS in form %s" % form
            for error in errors:
                print " - %s" % error
        if warnings:
            print "Found the following WARNINGS in form %s" % form
            for warning in warnings:
                print " - %s" % warning
