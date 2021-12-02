from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.urls import reverse
from corehq.apps.app_manager.models import Application, GlobalAppConfig
from corehq.apps.app_manager.xform import parse_xml
from corehq.apps.app_manager.exceptions import DangerousXmlException, XFormException
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    def __init__(self):
        self.entities_found = 0
        self.total_forms = 0

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--limit', default=0, type=int)

    def handle(self, all, limit, *args, **kwargs):
        if all:
            print('Searching for entities in ALL forms')
        else:
            print('Searching for entities in CURRENT forms')

        start_time = datetime.now()
        self.process_forms(all, limit)
        end_time = datetime.now()

        elapsed = end_time - start_time

        print(f'Found {self.entities_found} entities in {self.total_forms} forms')
        print(f'Completed search in {elapsed}')

    def process_forms(self, all, limit):
        get_apps = get_all_apps if all else get_current_apps

        for app in get_apps():
            for form in get_forms(app):
                if form_contains_entities(form):
                    handle_entity_form(form, app)
                    self.entities_found += 1
                self.total_forms += 1
                if limit > 0 and self.total_forms >= limit:
                    return


def get_all_apps():
    '''
    This looks at all apps, including previous versions.
    Note that this won't look at linked or remote apps
    '''
    app_types = [Application.__name__, f'{Application.__name__}-Deleted']
    for app_type in app_types:
        for app in get_app_type_results(app_type):
            yield app


def get_app_type_results(doc_type):
    num_processed = 0
    page_size = 10
    while True:
        results = Application.view('all_docs/by_doc_type',
            include_docs=True,
            reduce=False,
            startkey=[doc_type],
            endkey=[doc_type, {}],
            skip=num_processed,
            limit=page_size).all()

        if not results:
            break

        for app in results:
            yield app
        num_processed += len(results)


def get_current_apps():
    '''
    Only examine the most recent version of any application. This does look at linked and remote apps
    '''
    db = Application.get_db()
    query = GlobalAppConfig.objects.values_list('app_id', flat=True).order_by('id')
    paginator = Paginator(query, 100)
    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        app_ids = list(page.object_list)
        for app_doc in iter_docs(db, app_ids, chunksize=10):
            yield Application.wrap(app_doc)


def get_forms(app):
    for module in app.get_modules():
        for form in module.get_forms():
            yield form


def form_contains_entities(form):
    try:
        parse_xml(form.source)
    except DangerousXmlException:
        return True
    except XFormException:
        pass  # other parsing errors are ok

    return False


def handle_entity_form(form, app):
    print('Found entity')
    print(f'\tForm: {form.unique_id}, app {app._id}')
    if app.copy_of:
        print(f'\tApp is a copy of {app.copy_of}. Found on version {app.version}')
    protocol = settings.DEFAULT_PROTOCOL
    host = settings.BASE_ADDRESS
    url = reverse('get_xform_source', args=(app.domain, app._id, form.unique_id,))
    print(f'\tview document at: {protocol}://{host}{url}')
