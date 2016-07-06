import hashlib
from datetime import datetime

from couchdbkit import ResourceNotFound
from jsonobject.properties import ListProperty, BooleanProperty

from dimagi.ext.jsonobject import JsonObject, StringProperty, DateTimeProperty, DictProperty
from dimagi.utils.couch.database import get_db


class PaginationEventHandler(object):
    def page_start(self, total_emitted, *args, **kwargs):
        """Called prior to getting each page of data

        :param total_emitted: total count of data items yielded
        :param args: Argument list that was passed to the ``get_data_fn`` for this page
        :param kwargs: Keyword arguments that were passed to the ``get_data_fn`` for this page
        """
        pass

    def page_end(self, total_emitted, duration, *args, **kwargs):
        """Called at the end of each page of data

        :param total_emitted: total count of data items yielded
        :param duration: the duration in ms that it took to yield this page
        :param args: Argument list that was passed to the ``get_data_fn`` for this page
        :param kwargs: Keyword arguments that were passed to the ``get_data_fn`` for this page
        """
        pass


class DelegatingPaginationEventHandler(PaginationEventHandler):
    def __init__(self, handlers=None):
        self.handlers = handlers or []

    def add_handler(self, handler):
        self.handlers.append(handler)

    def page_start(self, total_emitted, *args, **kwargs):
        for handler in self.handlers:
            handler.page_start(total_emitted, *args, **kwargs)

    def page_end(self, total_emitted, duration, *args, **kwargs):
        for handler in self.handlers:
            handler.page_end(total_emitted, duration, *args, **kwargs)


def paginate_function(get_data_fn, next_args_fn, event_handler=PaginationEventHandler()):
    """
    Repeatedly call a data provider function with successive sets of arguments until
    no more data is returned.

    :param get_data_fn: function to paginate. Must return an list of data elements.
    :param next_args_fn: given the last data element of the previous ``get_data_fn`` call and the previous
    ``get_data_fn`` args and kwargs return the next set of arguments for ``get_data_fn``.
    Initially called with ``None`` to get the fist set of arguments.
    :param event_handler: class to be notified on page start and page end.
    """
    total_emitted = 0
    len_results = -1
    args, kwargs = next_args_fn(None)
    while len_results:
        event_handler.page_start(total_emitted, *args, **kwargs)
        results = get_data_fn(*args, **kwargs)
        start_time = datetime.utcnow()
        len_results = len(results)

        for item in results:
            yield item

        total_emitted += len_results
        event_handler.page_end(total_emitted, datetime.utcnow() - start_time, *args, **kwargs)

        if len_results:
            args, kwargs = next_args_fn(item, *args, **kwargs)


class ResumableIteratorState(JsonObject):
    doc_type = "ResumableIteratorState"
    _id = StringProperty()
    name = StringProperty()
    timestamp = DateTimeProperty()
    args = ListProperty()
    kwargs = DictProperty()
    retry = DictProperty()
    progress = DictProperty()
    complete = BooleanProperty(default=False)


class ResumableFunctionIterator(object):
    """Perform one-time resumable iteration over a data provider function.

    Iteration can be efficiently stopped and resumed.

    :param iteration_key: A unique key identifying the iteration. This
    key will be used in combination with `iteration_function` name to maintain state
    about an iteration that is in progress. The state will be maintained
    indefinitely unless it is removed with `discard_state()`.
    :param data_function: function to iterate over. Must return an list of data elements.
    :param args_function: given the last data element of the previous ``data_function`` call and the previous
    ``data_function`` args and kwargs return the next set of arguments for ``data_function``.
    Initially called with ``None`` to get the fist set of arguments.
    :param event_handler: Instance of ``PaginationEventHandler`` to be notified on page start and page end.
    """

    def __init__(self, iteration_key, data_function, args_function, event_handler=None):
        self.iteration_key = iteration_key
        self.data_function = data_function
        self.args_function = args_function
        self.event_handler = event_handler
        self.iteration_name = '{}/{}'.format(iteration_key, data_function.__name__)
        self.iteration_id = hashlib.sha1(self.iteration_name).hexdigest()

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
                    name=self.iteration_name,
                    timestamp=datetime.utcnow()
                )
        return self._state

    def __iter__(self):
        if self.state.complete:
            return

        resumable_args = self._get_resumable_args()
        event_handler = self._get_event_handler()

        for item in paginate_function(self.data_function, resumable_args, event_handler):
            yield item

        self.state.args = None
        self.state.kwargs = None
        self.state.complete = True
        self._save_state()

    def _get_event_handler(self):
        if self.event_handler:
            return DelegatingPaginationEventHandler([
                ResumableIteratorEventHandler(self),
                self.event_handler
            ])
        else:
            return ResumableIteratorEventHandler(self)

    def _get_resumable_args(self):
        resume = bool(getattr(self.state, '_rev', None))  # if there is a _rev then we're resuming
        resume_args = self.state.args
        resume_kwargs = self.state.kwargs

        def _resumable_args(item, *args, **kwargs):
            if resume and item is None:
                # return previous args on first call
                return resume_args, resume_kwargs

            return self.args_function(item, *args, **kwargs)

        return _resumable_args

    @property
    def progress_info(self):
        """Extra progress information

        This property can be used to store and retrieve extra progress
        information associated with the iteration. The information is
        persisted with the iteration state in couch.
        """
        return self.state.progress

    @progress_info.setter
    def progress_info(self, info):
        self.state.progress = info
        self._save_state()

    def _save_state(self):
        self.state.timestamp = datetime.utcnow()
        state_json = self.state.to_json()
        self.couch_db.save_doc(state_json)
        self._state = ResumableIteratorState(state_json)

    def discard_state(self):
        try:
            self.couch_db.delete_doc(self.iteration_id)
        except ResourceNotFound:
            pass
        self.__init__(
            self.iteration_key,
            self.data_function,
            self.args_function,
            self.event_handler
        )


class ResumableIteratorEventHandler(PaginationEventHandler):
    def __init__(self, iterator):
        self.iterator = iterator

    def page_start(self, total_emitted, *args, **kwargs):
        self.iterator.state.args = list(args)
        self.iterator.state.kwargs = kwargs
        self.iterator._save_state()
