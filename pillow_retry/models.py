import json
import traceback
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, IntegerProperty
from datetime import datetime

PILLOW_RETRY_VIEW = 'pillow_retry/pillow_errors'


def get_extra_args(limit, reduce, skip):
        extra_args = dict()
        if not reduce:
            extra_args.update(include_docs=True)
            if limit is not None:
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
    date_last_error = DateTimeProperty()
    attempts = IntegerProperty()
    error_message = StringProperty()
    error_type = StringProperty()
    error_traceback = StringProperty()

    def add_attempt(self, exception, traceb, date=None):
        self.attempts += 1
        self.date_last_error = date or datetime.now()
        self.error_message = exception.message
        self.error_type = name_path_from_object(exception)[1]
        self.error_traceback = "".join(traceback.format_tb(traceb))

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
            now = datetime.now()
            error = PillowError(
                _id=error_id,
                pillow=pillow_path,
                date_created=now,
                date_last_error=now,
                attempts=0
            )

        return error

    @classmethod
    def by_attempts(cls, min_attempts=0, max_attempts=5, reduce=False, limit=None, skip=0, descending=False):
        extra_args = get_extra_args(limit, reduce, skip)

        key = ['attempts']
        return cls.view(
            PILLOW_RETRY_VIEW,
            startkey=key + ([max_attempts, {}] if descending else [min_attempts]),
            endkey=key + ([min_attempts] if descending else [max_attempts, {}]),
            descending=descending,
            reduce=reduce,
            **extra_args
        ).all()

    @classmethod
    def by_date(cls, pillow=None, error_type=None, startdate=None, enddate=None, by_date_created=True, reduce=False,
                   limit=None, skip=0, descending=False):
        extra_args = get_extra_args(limit, reduce, skip)

        if startdate and isinstance(startdate, datetime):
            startdate = startdate.replace(microsecond=0).isoformat() + 'Z'
        if enddate and isinstance(enddate, datetime):
            enddate = enddate.replace(microsecond=0).isoformat() + 'Z'

        if pillow:
            if not isinstance(pillow, basestring):
                pillow = name_path_from_object(pillow)[1]
            key_selector = ['pillow']
        elif error_type:
            if not isinstance(pillow, basestring):
                error_type = name_path_from_object(error_type)[1]
            key_selector = ['type']
        else:
            key_selector = []

        key_selector += ['created'] if by_date_created else ['modified']
        key = [' '.join(key_selector)]
        if pillow or error_type:
            key += [pillow] if pillow else [error_type]

        if descending:
            start = [enddate, {}] if enddate else [{}]
            end = [startdate, {}] if startdate else []
        else:
            start = [startdate] if startdate else []
            end = [enddate, {}] if enddate else [{}]

        return cls.view(
            PILLOW_RETRY_VIEW,
            startkey=key + start,
            endkey=key + end,
            descending=descending,
            reduce=reduce,
            **extra_args
        ).all()


