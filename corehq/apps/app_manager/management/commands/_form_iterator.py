import signal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from jsonobject.exceptions import BadValueError, WrappingAttributeError
from corehq.apps.app_manager.models import Application, GlobalAppConfig
from dimagi.utils.couch.database import iter_docs
from corehq.util.log import with_progress_bar
from corehq.util.doc_processor.couch import resumable_view_iterator


class FormIteratorCommandBase(BaseCommand):
    help = '''
    Searches through application forms to determine if XML entities exist.
    Resumable. Call with --reset if you wish to start a fresh run
    '''

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
            help='check all applications, rather than only current ones')
        parser.add_argument('--limit', default=0, type=int, help='terminate after LIMIT forms')
        parser.add_argument('--reset', action='store_true', help='trigger a fresh run')
        parser.add_argument('--path', default='output.log', help='the path to write log output')
        parser.add_argument('--batchsize', default=10, type=int, help='number of apps to pull simultaneously')

    def handle(self, all, limit, reset, path, batchsize, *args, **kwargs):
        write_mode = 'w' if reset else 'a'  # Only overwrite on fresh runs

        # NOTE: Outputting to a file, rather than stdout for some messages due to the progress bar.
        # Because the progress bar alters stdout, just using 'tee' doesn't produce a good log file,
        # Hence the support for a separate log file here
        with open(path, write_mode) as f:
            self.log_file = f
            self.setup_interrupt_handler()

            if all:
                self.broadcast('Searching in ALL forms')
            else:
                self.broadcast('Searching in CURRENT forms')

            self.start_time = datetime.now()
            self.process_forms(all, limit, reset, batchsize)
            self.report_results()

    def process_forms(self, all, limit, reset, batchsize):

        # This method is meant to be overridden

        raise NotImplementedError()

    def report_results(self):
        # Default result statement - override with more detailed specs encouraged

        elapsed = datetime.now() - self.start_time
        self.broadcast(f'Processed {self.total_forms} forms in {elapsed}')

    def setup_interrupt_handler(self):
        def interrupt_handler(signum, frame):
            self.report_results()
            exit(1)

        signal.signal(signal.SIGINT, interrupt_handler)

    def broadcast(self, msg):
        '''Send a message to both stdout and the file'''
        print(msg)
        print(msg, file=self.log_file)

    def get_all_apps(self, reset=False, batchsize=10):
        '''
        This looks at all apps, including previous versions.
        Note that this won't look at linked or remote apps
        '''
        db = Application.get_db()
        keys = [[Application.__name__], [f'{Application.__name__}-Deleted']]
        view_name = 'all_docs/by_doc_type'
        raw_iter = resumable_view_iterator(db, self.iteration_key, view_name, view_keys=keys, chunk_size=batchsize,
            full_row=True)
        if reset:
            raw_iter.discard_state()

        modified_start_key, keys = get_keys_to_search(keys, raw_iter)

        count = get_remaining_app_count(db, view_name, keys, modified_start_key)

        app_iter = (wrapped_app for wrapped_app in (self.wrap_app(x) for x in raw_iter) if wrapped_app)
        return with_progress_bar(app_iter, count)

    def wrap_app(self, fetched_row):
        id = fetched_row['id']
        raw_app = fetched_row['doc']
        if not raw_app:
            print(f'no associated app found for: {id}', file=self.log_file)
            return None

        try:
            return Application.wrap(raw_app)
        except (BadValueError, WrappingAttributeError, ValueError, AssertionError):
            print(f'could not wrap app: {raw_app["_id"]}', file=self.log_file)
            return None


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


def get_current_apps(reset=False, batchsize=10):
    '''
    Only examine the most recent version of any application. This does look at linked and remote apps.
    Note that this doesn't support resumable execution, as the effort was out of scope,
    and therefore reset is unused.
    '''
    query = GlobalAppConfig.objects.values_list('app_id', flat=True).order_by('id')
    count = query.count()
    iter = get_current_apps_iter(query, batchsize)

    return with_progress_bar(iter, count)


def get_current_apps_iter(query, batchsize):
    db = Application.get_db()
    paginator = Paginator(query, 100)
    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        app_ids = list(page.object_list)
        for app_doc in iter_docs(db, app_ids, chunksize=batchsize):
            yield Application.wrap(app_doc)


def get_forms(app):
    for module in app.get_modules():
        yield from module.get_forms()
