from django.core.management.base import LabelCommand, CommandError
from django.conf import settings

from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.util.view_utils import reverse

from couchdbkit import ResourceNotFound


class Command(LabelCommand):
    help = "Bootstrap an Application with two modules in a given domain."
    args = "<domain> <app-name>"
    label = ""

    def handle(self, *args, **options):

        if len(args) != 2:
            raise CommandError('Usage: manage.py bootstrap_app <domain> <app-name>')
        domain_name, app_name = args

        try:
            Domain.get_by_name(domain_name)
        except ResourceNotFound:
            raise CommandError("Domain with name '{domain_name}' not found".format(
                domain_name=domain_name
            ))

        self.create_two_module_app(domain_name, app_name)

        if not getattr(settings, 'BASE_ADDRESS', None):
            print ("Warning: You must set BASE_ADDRESS setting "
                   "in your localsettings.py file in order for commcare-hq "
                   "to be able to generate absolute urls. "
                   "This is necessary for a number of features.")

    def create_two_module_app(self, domain_name, app_name):

        app = Application.new_app(domain_name, app_name, application_version=APP_V2)
        app.add_module(Module.new_module('Module 1', None))
        app.add_module(Module.new_module('Module 2', None))

        for m_id in range(2):
            app.new_form(m_id, "Form", None)

        app.save()

        print "Application {app_name}: {app_url} created in domain {domain_name}".format(
            app_name=app_name,
            app_url=reverse('view_app', args=[domain_name, app._id], absolute=True),
            domain_name=domain_name
        )
