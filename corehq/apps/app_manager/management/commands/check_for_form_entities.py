import signal
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.urls import reverse
from corehq.apps.app_manager.models import Application, GlobalAppConfig
from corehq.apps.app_manager.xform import parse_xml
from corehq.apps.app_manager.exceptions import DangerousXmlException, XFormException
from dimagi.utils.couch.database import iter_docs
from corehq.util.log import with_progress_bar
from corehq.util.doc_processor.couch import resumable_view_iterator


class Command(BaseCommand):
    help = '''
    Searches through application forms to determine if XML entities exist.
    Resumable. Call with --reset if you wish to start a fresh run
    '''

    def __init__(self):
        self.entities_found = 0
        self.total_forms = 0
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
            help='check all applications, rather than only current ones')
        parser.add_argument('--limit', default=0, type=int, help='terminate after LIMIT forms')
        parser.add_argument('--reset', action='store_true', help='trigger a fresh run')
        parser.add_argument('--path', default='output.log', help='the path to write log output')

    def handle(self, all, limit, reset, path, *args, **kwargs):
        write_mode = 'w' if reset else 'a'  # Only overwrite on fresh runs

        # NOTE: Outputting to a file, rather than stdout for some messages due to the progress bar.
        # Because the progress bar alters stdout, just using 'tee' doesn't produce a good log file,
        # Hence the support for a separate log file here
        with open(path, write_mode) as f:
            self.log_file = f
            self.setup_interrupt_handler()

            if all:
                self.broadcast('Searching for entities in ALL forms')
            else:
                self.broadcast('Searching for entities in CURRENT forms')

            self.start_time = datetime.now()
            self.process_forms(all, limit, reset)
            self.report_results()

    def process_forms(self, all, limit, reset):
        get_apps = get_all_apps if all else get_current_apps

        for app in get_apps(reset):
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

    def setup_interrupt_handler(self):
        def interrupt_handler(signum, frame):
            self.report_results(self.log_file)
            exit(1)

        signal.signal(signal.SIGINT, interrupt_handler)

    def broadcast(self, msg):
        '''Send a message to both stdout and the file'''
        print(msg)
        print(msg, file=self.log_file)


def get_all_apps(reset=False):
    '''
    This looks at all apps, including previous versions.
    Note that this won't look at linked or remote apps
    '''
    db = Application.get_db()
    keys = [[Application.__name__], [f'{Application.__name__}-Deleted']]
    view_name = 'all_docs/by_doc_type'
    raw_iter = resumable_view_iterator(db, 'doc_type', view_name, view_keys=keys, chunk_size=10)
    if reset:
        raw_iter.discard_state()

    modified_start_key, keys = get_keys_to_search(keys, raw_iter)

    count = get_remaining_app_count(db, view_name, keys, modified_start_key)

    app_iter = (Application.wrap(x) for x in raw_iter)
    return with_progress_bar(app_iter, count)


def get_keys_to_search(keys, iterator):
    # Check for existing progress with the resumable iterator
    # This is working with the assumption that the iterator will iterate through the keys in the order
    # they are specified. This is brittle, but I don't have a better solution without reworking
    # the resumable iterator. This method knows FAR too much of the internals of the resumable iterator
    if 'startkey' not in iterator.state.kwargs:
        return (None, keys)

    startkey = list(iterator.state.kwargs['startkey'])
    base_start = startkey[:-1]
    index = keys.index(base_start)
    keys = keys[index:]
    return (startkey, keys)


def get_remaining_app_count(db, view_name, keys, modified_start_key):
    count = 0
    for index, key in enumerate(keys):
        if index == 0 and modified_start_key:
            startkey = modified_start_key
        else:
            startkey = key

        endkey = key + [{}]
        query = db.view(view_name, reduce=True, startkey=startkey, endkey=endkey)
        count += query.first()['value']

    return count


def get_current_apps(reset=False):
    '''
    Only examine the most recent version of any application. This does look at linked and remote apps.
    Note that this doesn't support resumable execution, as the effort was out of scope,
    and therefore reset is unused.
    '''
    query = GlobalAppConfig.objects.values_list('app_id', flat=True).order_by('id')
    count = query.count()
    iter = get_current_apps_iter(query)

    return with_progress_bar(iter, count)


def get_current_apps_iter(query):
    db = Application.get_db()
    paginator = Paginator(query, 100)
    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        app_ids = list(page.object_list)
        for app_doc in iter_docs(db, app_ids, chunksize=10):
            yield Application.wrap(app_doc)


def get_forms(app):
    for module in app.get_modules():
        yield from module.get_forms()


def form_contains_entities(form):
    try:
        parse_xml(form.source)
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
