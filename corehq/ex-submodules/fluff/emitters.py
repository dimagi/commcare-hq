import functools
import datetime
from .exceptions import EmitterValidationError


REDUCE_TYPES = set(['sum', 'count', 'min', 'max', 'sumsqr'])


class base_emitter(object):
    fluff_emitter = ''

    def __init__(self, reduce_type='sum'):
        assert reduce_type in REDUCE_TYPES, 'Unknown reduce type'
        self.reduce_type = reduce_type

    def __call__(self, fn):
        @functools.wraps(fn)
        def wrapped_f(*args):
            generator = fn(*args)
            for v in generator:
                if isinstance(v, dict):
                    if 'value' not in v:
                        v['value'] = 1
                    if v.get('group_by') is None:
                        v['group_by'] = None
                    elif isinstance(v['group_by'], tuple):
                        v['group_by'] = list(v['group_by'])
                    elif not isinstance(v['group_by'], list):
                        v['group_by'] = [v['group_by']]
                elif isinstance(v, list):
                    v = dict(date=v[0], value=v[1], group_by=None)
                else:
                    v = dict(date=v, value=1, group_by=None)
                try:
                    self.validate(v)
                except EmitterValidationError as e:
                    generator.throw(e)
                yield v

        wrapped_f._reduce_type = self.reduce_type
        wrapped_f._fluff_emitter = self.fluff_emitter
        return wrapped_f

    def validate(self, value):
        pass


class custom_date_emitter(base_emitter):
    fluff_emitter = 'date'

    def validate(self, value):
        def validate_date(dateval):
            if not isinstance(dateval, (datetime.date, datetime.datetime)):
                raise EmitterValidationError(
                    'Emitted value must be '
                    'a date or datetime object: {}'.format(
                        dateval
                    )
                )

        validate_date(value.get('date'))
        if isinstance(value['date'], datetime.datetime):
            value['date'] = value['date'].date()


class custom_null_emitter(base_emitter):
    fluff_emitter = 'null'

    def validate(self, value):
        if isinstance(value, dict):
            if 'date' not in value:
                value['date'] = None
            else:
                if value['date'] is not None:
                    raise EmitterValidationError(
                        'Emitted value must be None: {}'.format(value['date']))


date_emitter = custom_date_emitter()
null_emitter = custom_null_emitter()
