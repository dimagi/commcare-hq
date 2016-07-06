import datetime


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
    Repeatedly call a data production function with successive sets of arguments until
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
        start_time = datetime.datetime.utcnow()
        len_results = len(results)

        for item in results:
            yield item

        total_emitted += len_results
        event_handler.page_end(total_emitted, datetime.datetime.utcnow() - start_time, *args, **kwargs)

        if len_results:
            args, kwargs = next_args_fn(item, *args, **kwargs)
