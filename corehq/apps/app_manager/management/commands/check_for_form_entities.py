from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.urls import reverse
from corehq.apps.app_manager.xform import parse_xml
from corehq.apps.app_manager.exceptions import DangerousXmlException, XFormException

from ._form_iterator import FormIteratorCommandBase, get_current_apps, get_forms


class Command(FormIteratorCommandBase):

    def __init__(self):
        self.entities_found = 0
        self.total_forms = 0
        self.start_time = None
        self.iteration_key = __name__

    def process_forms(self, all, limit, reset, batchsize):
        get_apps = self.get_all_apps if all else get_current_apps

        for app in get_apps(reset, batchsize):
            for form in get_forms(app):
                if form_contains_entities(form):
                    handle_entity_form(form, app, self.log_file)
                    self.entities_found += 1
                self.total_forms += 1
                if limit > 0 and self.total_forms >= limit:
                    return

    def report_results(self):
        elapsed = datetime.now() - self.start_time
        self.broadcast(f'Found {self.entities_found} entities in {self.total_forms} forms')
        self.broadcast(f'Completed search in {elapsed}')


def form_contains_entities(form):
    try:
        source = form.source
    except ResourceNotFound:
        return False  # unable to resolve the form

    try:
        parse_xml(source)
    except DangerousXmlException:
        return True
    except XFormException:
        pass  # other parsing errors are ok

    return False


def handle_entity_form(form, app, log_file):
    print('Found entity', file=log_file)
    print(f'\tForm: {form.unique_id}, app {app._id}', file=log_file)
    if app.copy_of:
        print(f'\tApp is a copy of {app.copy_of}. Found on version {app.version}', file=log_file)
    protocol = settings.DEFAULT_PROTOCOL
    host = settings.BASE_ADDRESS
    url = reverse('get_xform_source', args=(app.domain, app._id, form.unique_id,))
    print(f'\tview document at: {protocol}://{host}{url}', file=log_file)
