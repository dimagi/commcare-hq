import hashlib
from datetime import datetime

from couchdbkit import ResourceNotFound
from jsonobject.properties import ListProperty, JsonArray, JsonSet, JsonDict

from dimagi.ext.jsonobject import JsonObject, StringProperty, DateTimeProperty, DictProperty
from dimagi.utils.couch.database import get_db, retry_on_couch_error


class PaginationEventHandler(object):
    def page_start(self, total_emitted, *args, **kwargs):
        """Called prior to getting each page of data

        :param total_emitted: total count of data items yielded
        :param args: Argument list that was passed to the ``data_function`` for this page
        :param kwargs: Keyword arguments that were passed to the ``data_function`` for this page
        """
        pass

    def page_exception(self, exception):
        """ Called on the load if it raises an exception

        :param exception: the exception that was raised

        returns a boolean of whether the exception was handled
        """
        return False

    def page(self, results):
        """Called just after loading a page of results, but before processing it

        :param results: The page of results.
        """
        pass

    def page_end(self, total_emitted, duration, *args, **kwargs):
        """Called at the end of each page of data

        :param total_emitted: total count of data items yielded
        :param duration: the duration in ms that it took to yield this page
        :param args: Argument list that was passed to the ``data_function`` for this page
        :param kwargs: Keyword arguments that were passed to the ``data_function`` for this page
        """
        pass

    def stop(self):
        """Called at the end of the iteration"""
        pass


class DelegatingPaginationEventHandler(PaginationEventHandler):
    def __init__(self, handlers=None):
        self.handlers = handlers or []

    def add_handler(self, handler):
        self.handlers.append(handler)

    def page_start(self, total_emitted, *args, **kwargs):
        for handler in self.handlers:
            handler.page_start(total_emitted, *args, **kwargs)

    def page_exception(self, exception):
        return any(h.page_exception(exception) for h in self.handlers)

    def page(self, results):
        for handler in self.handlers:
            handler.page(results)

    def page_end(self, total_emitted, duration, *args, **kwargs):
        for handler in self.handlers:
            handler.page_end(total_emitted, duration, *args, **kwargs)

    def stop(self):
        for handler in self.handlers:
            handler.stop()


class ArgsProvider(object):
    def get_initial_args(self):
        """Return the initial set of args and kwargs

        :returns: tuple of args list and kwargs dict"""
        raise NotImplementedError

    def adjust_results(self, results, args, kwargs):
        """Adjust results given args and kwargs used to retrieve them

        :param results: list of results loaded with `args` and `kwargs`.
        :param args: args used to load results.
        :param kwargs: kwargs used to load results.
        :returns: adjusted list of results.
        """
        return results

    def get_next_args(self, last_item, *last_args, **last_kwargs):
        """Return the next set of args and kwargs

        :returns: tuple of args list and kwargs dict
        :raises: StopIteration to end the iteration
        """
        raise StopIteration


class ArgsListProvider(ArgsProvider):
    """Argument provider for iterating over a function by providing
    a sequence of keyword arguments.
    :param kwargs_list: Sequence of keyword arguments to iterate over.
    """
    def __init__(self, kwargs_list):
        self.kwargs_list = list(kwargs_list)

    def get_initial_args(self):
        return [], self.kwargs_list[0]

    def get_next_args(self, result, *last_args, **last_kwargs):
        kwargs_index = self.kwargs_list.index(last_kwargs) + 1
        self.kwargs_list = self.kwargs_list[kwargs_index:]
        try:
            next_kwargs = self.kwargs_list[0]
        except IndexError:
            raise StopIteration
        return last_args, next_kwargs


def paginate_function(data_function, args_provider, event_handler=None):
    """
    Repeatedly call a data provider function with successive sets of arguments provided
    by the ``args_provider``

    :param data_function: function to paginate. Must return an list of data elements.
    :param args_provider: An instance of the ``ArgsProvider`` class which is used to
    generate the arguments that get passed to ``data_function``
    :param event_handler: class to be notified on page start and page end.
    """
    event_handler = event_handler or PaginationEventHandler()
    total_emitted = 0
    args, kwargs = args_provider.get_initial_args()

    while True:
        event_handler.page_start(total_emitted, *args, **kwargs)
        results = data_function(*args, **kwargs)
        start_time = datetime.utcnow()

        try:
            results = list(results)
        except Exception as e:
            if event_handler.page_exception(e):
                continue
            raise

        results = args_provider.adjust_results(results, args, kwargs)
        event_handler.page(results)
        yield from results

        total_emitted += len(results)
        event_handler.page_end(total_emitted, datetime.utcnow() - start_time, *args, **kwargs)

        item = results[-1] if results else None
        try:
            args, kwargs = args_provider.get_next_args(item, *args, **kwargs)
        except StopIteration:
            event_handler.stop()
            break


class ResumableIteratorState(JsonObject):
    doc_type = "ResumableIteratorState"
    _id = StringProperty()
    name = StringProperty()
    timestamp = DateTimeProperty()
    args = ListProperty()
    kwargs = DictProperty()
    progress = DictProperty()

    def is_resume(self):
        return bool(getattr(self, '_rev', None))


def unpack_jsonobject(json_object):
    if isinstance(json_object, JsonArray):
        return [unpack_jsonobject(x) for x in json_object]
    elif isinstance(json_object, JsonSet):
        return {unpack_jsonobject(x) for x in json_object}
    elif isinstance(json_object, JsonDict):
        return {
            unpack_jsonobject(k): unpack_jsonobject(v) for k, v in json_object.items()
        }
    return json_object


class ResumableArgsProvider(ArgsProvider):
    def __init__(self, iterator_state, args_provider):
        self.args_provider = args_provider
        self.resume = iterator_state.is_resume()
        self.resume_args = iterator_state.to_json()['args']
        self.resume_kwargs = iterator_state.to_json()['kwargs']

    def get_initial_args(self):
        if self.resume:
            return unpack_jsonobject(self.resume_args), unpack_jsonobject(self.resume_kwargs)
        return self.args_provider.get_initial_args()

    def adjust_results(self, results, args, kwargs):
        return self.args_provider.adjust_results(results, args, kwargs)

    def get_next_args(self, last_item, *last_args, **last_kwargs):
        return self.args_provider.get_next_args(last_item, *last_args, **last_kwargs)


class ResumableFunctionIterator(object):
    """Perform one-time resumable iteration over a data provider function.

    Iteration can be efficiently stopped and resumed.

    :param iteration_key: A unique key identifying the iteration. This
    key will be used in combination with `iteration_function` name to
    maintain state about an iteration that is in progress. The state
    will be maintained indefinitely unless it is removed with
    `discard_state()`.
    :param data_function: function to iterate over. Must return an list
    of data elements.
    :param args_provider: An instance of the ``ArgsProvider`` class.
    :param event_handler: Instance of ``PaginationEventHandler`` to be
    notified on page events. May raise ``StopToResume`` to terminate the
    iteration immediately (it may be resumed later).
    """

    def __init__(self, iteration_key, data_function, args_provider, event_handler=None):
        self.iteration_key = iteration_key
        self.data_function = data_function
        self.args_provider = args_provider
        self.event_handler = event_handler
        self.iteration_id = hashlib.sha1(self.iteration_key.encode('utf-8')).hexdigest()

        self.couch_db = get_db('meta')
        self._state = None

    @property
    def state(self):
        if not self._state:
            try:
                self._state = ResumableIteratorState(self.couch_db.get(self.iteration_id))
            except ResourceNotFound:
                # new iteration
                self._state = ResumableIteratorState(
                    _id=self.iteration_id,
                    name=self.iteration_key,
                    timestamp=datetime.utcnow()
                )
        return self._state

    def __iter__(self):
        if getattr(self.state, "complete", False):
            # Legacy: do not try to resume completed iteration
            return

        resumable_args = ResumableArgsProvider(self.state, self.args_provider)
        event_handler = self._get_event_handler()

        try:
            yield from paginate_function(self.data_function, resumable_args, event_handler)
        except StopToResume:
            return

        self._save_state()

    def _get_event_handler(self):
        if self.event_handler:
            return DelegatingPaginationEventHandler([
                self.event_handler,  # first so it can mutate iterator state
                ResumableIteratorEventHandler(self),
            ])
        else:
            return ResumableIteratorEventHandler(self)

    def get_iterator_detail(self, key):
        """Get the detail value value for the given key
        """
        return self.state.progress.get(key, None)

    def set_iterator_detail(self, key, value):
        """Set the detail value for the given key.

        This can be used to store and retrieve extra
        information associated with the iteration. The information is
        persisted with the iteration state in couch.
        """
        self.state.progress[key] = value
        self._save_state()

    def _save_state(self):
        self.state.timestamp = datetime.utcnow()
        state_json = self.state.to_json()
        self._save_state_json(state_json)
        self._state = ResumableIteratorState(state_json)

    @retry_on_couch_error
    def _save_state_json(self, state_json):
        self.couch_db.save_doc(state_json)

    def discard_state(self):
        try:
            self.couch_db.delete_doc(self.iteration_id)
        except ResourceNotFound:
            pass
        self.__init__(
            self.iteration_key,
            self.data_function,
            self.args_provider,
            self.event_handler
        )


class ResumableIteratorEventHandler(PaginationEventHandler):
    """Used to save the iteration progress at the beginning
    of each page.
    """
    def __init__(self, iterator):
        self.iterator = iterator

    def page_start(self, total_emitted, *args, **kwargs):
        self.iterator.state.args = list(args)
        self.iterator.state.kwargs = kwargs
        self.iterator._save_state()


class StopToResume(Exception):
    pass
