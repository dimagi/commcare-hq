import datetime
import logging
import time
from django.utils.module_loading import import_string


class DjangoModelHandler(logging.Handler):
    """
    A logging handler that logs to a Django Model.

    DjangoModelHandler assumes that the Model class has a property named "timestamp" and sets it to record.created
    (without timezone). It uses record.args for the rest of the Model's properties.

    .. NOTE: DjangoModelHandler.emit() ignores record.exc_info. In order to log exceptions, subclasses should move
             any required data from record.exc_info into record.args before calling DjangoModelHandler.emit()

    e.g. to log values for properties named "some_property" and "another_property" you could use something like:

    >>> LOGGING = {
    ...     'handlers': {
    ...         'my_model': {
    ...             'class': 'handlers.DjangoModelHandler',
    ...             'level': 'DEBUG',
    ...             'model_class': MyModel,
    ...         }
    ...     },
    ...     'loggers': {
    ...         'my_logger': {
    ...             'handlers': 'my_model',
    ...             'level': 'DEBUG',
    ...         }
    ...     },
    ... }
    >>> logger = logging.getLogger('my_logger')
    >>> logger.debug({'some_property': 'xyzzy', 'another_property': 6.283185})

    """
    def __init__(self, model_class, *args, **kwargs):
        super(DjangoModelHandler, self).__init__(*args, **kwargs)
        self._model_class = model_class

    @property
    def model_class(self):
        """
        Lazyload model class so that we can configure it in settings.py before we can load app modules
        """
        if isinstance(self._model_class, basestring):
            self._model_class = import_string(self._model_class)
        return self._model_class

    def emit(self, record):
        created = time.localtime(record.created)
        kwargs = dict(record.args, timestamp=datetime.datetime(
            year=created.tm_year,
            month=created.tm_mon,
            day=created.tm_mday,
            hour=created.tm_hour,
            minute=created.tm_min,
            second=created.tm_sec,
        ))
        self.model_class.objects.create(**kwargs)
