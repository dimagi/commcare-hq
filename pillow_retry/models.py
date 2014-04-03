import json
import traceback
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, IntegerProperty, BooleanProperty
from datetime import datetime, timedelta
from django.conf import settings
import math
from dimagi.utils.parsing import json_format_datetime

PILLOW_ERRORS_VIEW = 'pillow_retry/pillow_errors'
BY_NEXT_ATTEMPT_VIEW = 'pillow_retry/by_next_attempt'


def _get_extra_args(limit, reduce, skip):
        extra_args = dict()
        if not reduce and limit is not None:
                extra_args.update(
                    limit=limit,
                    skip=skip
                )
        return extra_args

def name_path_from_object(obj):
        name = obj.__class__.__name__
        path = "{0}.{1}".format(obj.__class__.__module__, name)
        return name, path


class PillowError(Document):
    pillow = StringProperty()
    date_created = DateTimeProperty()
    date_last_attempt = DateTimeProperty()
    date_next_attempt = DateTimeProperty()
    total_attempts = IntegerProperty(default=0)
    current_attempt = IntegerProperty(default=0)
    error_message = StringProperty()
    error_type = StringProperty()
    error_traceback = StringProperty()

    def add_attempt(self, exception, traceb, date=None):
        self.current_attempt += 1
        self.total_attempts += 1
        self.date_last_attempt = date or datetime.utcnow()
        self.error_message = exception.message
        self.error_type = name_path_from_object(exception)[1]
        self.error_traceback = "".join(traceback.format_tb(traceb))

        if self.current_attempt <= settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS:
            time_till_next = settings.PILLOW_RETRY_REPROCESS_INTERVAL * math.pow(self.current_attempt, settings.PILLOW_RETRY_BACKOFF_FACTOR)
            self.date_next_attempt = self.date_last_attempt + timedelta(minutes=time_till_next)
        else:
            self.date_next_attempt = None

    def reset_attempts(self):
        self.current_attempt = 0
        self.date_next_attempt = datetime.utcnow()

    @property
    def original_id(self):
        return self.get_id.split('__')[1]

    @classmethod
    def get_or_create(cls, change, pillow):
        pillow_name, pillow_path = name_path_from_object(pillow)
        error_id = '{0}__{1}'.format(pillow_name, change['id'])

        try:
            error = cls.get(error_id)
        except ResourceNotFound:
            error = None

        if not error:
            now = datetime.utcnow()
            error = PillowError(
                _id=error_id,
                pillow=pillow_path,
                date_created=now,
                date_last_attempt=now,
                date_next_attempt=now,
            )

        return error

    @classmethod
    def get_errors_to_process(cls, utcnow, reduce=False, limit=None, skip=0, include_docs=False):
        extra_args = _get_extra_args(limit, reduce, skip)
        return cls.view(
            BY_NEXT_ATTEMPT_VIEW,
            startkey=[],
            endkey=[json_format_datetime(utcnow), {}],
            reduce=reduce,
            include_docs=(include_docs and not reduce),
            **extra_args
        )

    @classmethod
    def _get_list(cls, name):
        key = ['{0} created'.format(name)]
        rows = cls.view(
            PILLOW_ERRORS_VIEW,
            startkey=key,
            endkey=key + [{}],
            group_level=2
        ).all()

        return [row['key'][1] for row in rows]

    @classmethod
    def get_pillows(cls):
        return cls._get_list('pillow')

    @classmethod
    def get_error_types(cls):
        return cls._get_list('type')

    @classmethod
    def get_errors(cls, pillow=None, error_type=None, startdate=None, enddate=None, by_date_created=True,
                   reduce=False, limit=None, skip=0, descending=False, include_docs=False):
        """
        This function allows you to query the pillow_errors view.

        The view emits 8 records with keys as shown below which allows the records to be queried
         * by date created or date modified
         * by pillow and date
         * by error type and date
         * by pillow, error_type and date

         Keys emitted from the view:
         * ['created', date_created]
         * ['modified', date_last_attempt]
         * ['pillow created', pillow, date_created]
         * ['pillow modified', pillow,m date_last_attempt]
         * ['type created', error_type, date_created]
         * ['type modified', error_type, date_last_attempt]
         * ['pillow type created', pillow, error_type, date_created]
         * ['pillow type modified', pillow, error_type, date_last_attempt]
        """
        extra_args = _get_extra_args(limit, reduce, skip)

        if startdate and isinstance(startdate, datetime):
            startdate = startdate.replace(microsecond=0).isoformat() + 'Z'
        if enddate and isinstance(enddate, datetime):
            enddate = enddate.replace(microsecond=0).isoformat() + 'Z'

        # determine whether to query by pillow, error type or just by date
        key_selector = []
        key_values = []
        if pillow:
            if not isinstance(pillow, basestring):
                pillow = name_path_from_object(pillow)[1]
            key_selector.append('pillow')
            key_values.append(pillow)
        if error_type:
            if not isinstance(error_type, basestring):
                error_type = name_path_from_object(error_type)[1]
            key_selector.append('type')
            key_values.append(error_type)

        # query by date created or modified
        key_selector += ['created'] if by_date_created else ['modified']

        # generate base key
        key = [' '.join(key_selector)] + key_values

        # add date ranges if necessary
        if descending:
            start = [enddate, {}] if enddate else [{}]
            end = [startdate, {}] if startdate else []
        else:
            start = [startdate] if startdate else []
            end = [enddate, {}] if enddate else [{}]

        return cls.view(
            PILLOW_ERRORS_VIEW,
            startkey=key + start,
            endkey=key + end,
            descending=descending,
            reduce=reduce,
            include_docs=(include_docs and not reduce),
            **extra_args
        )


