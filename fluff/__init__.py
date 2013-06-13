from collections import defaultdict
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django import schema
import datetime
from dimagi.utils.parsing import json_format_date
from dimagi.utils.read_only import ReadOnlyObject
from fluff import exceptions
from pillowtop.listener import BasicPillow
from .signals import indicator_document_updated
import fluff.sync_couchdb


REDUCE_TYPES = set(['sum', 'count', 'min', 'max', 'sumsqr'])


class base_emitter(object):
    fluff_emitter = ''

    def __init__(self, reduce_type='count'):
        assert reduce_type in REDUCE_TYPES, 'Unknown reduce type'
        self.reduce_type = reduce_type

    def __call__(self, fn):
        def wrapped_f(*args):
            for v in fn(*args):
                if not isinstance(v, list):
                    v = [v, 1]

                self.validate(v)
                yield v

        wrapped_f._reduce_type = self.reduce_type
        wrapped_f._fluff_emitter = self.fluff_emitter
        return wrapped_f

    def validate(self, value):
        pass


class custom_date_emitter(base_emitter):
    fluff_emitter = 'date'

    def validate(self, value):
        assert value[0] is not None
        assert isinstance(value[0], (datetime.date, datetime.datetime))
        if isinstance(value[0], datetime.datetime):
            value[0] = value[0].date()


class custom_null_emitter(base_emitter):
    fluff_emitter = 'null'

    def validate(self, value):
        assert value[0] is None

date_emitter = custom_date_emitter()
null_emitter = custom_null_emitter()


def filter_by(fn):
    fn._fluff_filter = True
    return fn


class CalculatorMeta(type):
    _counter = 0

    def __new__(mcs, name, bases, attrs):
        emitters = set()
        filters = set()
        parents = [p for p in bases if isinstance(p, CalculatorMeta)]
        for attr in attrs:
            if getattr(attrs[attr], '_fluff_emitter', None):
                emitters.add(attr)
            if getattr(attrs[attr], '_fluff_filter', False):
                filters.add(attr)

        # needs to inherit emitters and filters from all parents
        for parent in parents:
            emitters.update(parent._fluff_emitters)
            filters.update(parent._fluff_filters)

        cls = super(CalculatorMeta, mcs).__new__(mcs, name, bases, attrs)
        cls._fluff_emitters = emitters
        cls._fluff_filters = filters
        cls._counter = mcs._counter
        mcs._counter += 1
        return cls


class Calculator(object):
    __metaclass__ = CalculatorMeta

    window = None

    # set by IndicatorDocumentMeta
    fluff = None
    slug = None

    # set by CalculatorMeta
    _fluff_emitters = None
    _fluff_filters = None

    def __init__(self, window=None):
        if window is not None:
            self.window = window
        if not isinstance(self.window, datetime.timedelta):
            if any(getattr(self, e)._fluff_emitter == 'date' for e in self._fluff_emitters):
                # if window is set to None, for instance
                # fail here and not whenever that's run into below
                raise NotImplementedError(
                    'window must be timedelta, not %s' % type(self.window))

    def filter(self, item):
        return True

    def to_python(self, value):
        return value

    def calculate(self, item):
        passes_filter = self.filter(item) and all(
            (getattr(self, slug)(item) for slug in self._fluff_filters)
        )
        values = {}
        for slug in self._fluff_emitters:
            fn = getattr(self, slug)
            values[slug] = (
                list(fn(item))
                if passes_filter else []
            )
        return values

    def get_result(self, key, reduce=True):
        result = {}
        for emitter_name in self._fluff_emitters:
            shared_key = [self.fluff._doc_type] + key + [self.slug, emitter_name]
            emitter = getattr(self, emitter_name)
            emitter_type = emitter._fluff_emitter
            q_args = {
                'reduce': reduce,
            }
            if emitter_type == 'date':
                now = self.fluff.get_now()
                start = now - self.window
                end = now
                if start > end:
                    q_args['descending'] = True
                q = self.fluff.view(
                    'fluff/generic',
                    startkey=shared_key + [json_format_date(start)],
                    endkey=shared_key + [json_format_date(end)],
                    **q_args
                ).all()
            elif emitter_type == 'null':
                q = self.fluff.view(
                    'fluff/generic',
                    key=shared_key + [None],
                    **q_args
                ).all()
            else:
                raise exceptions.EmitterTypeError(
                    'emitter type %s not recognized' % emitter_type
                )

            if reduce:
                try:
                    result[emitter_name] = q[0]['value'][emitter._reduce_type]
                except IndexError:
                    result[emitter_name] = 0
            else:
                def strip(id_string):
                    prefix = '%s-' % self.fluff.__name__
                    assert id_string.startswith(prefix)
                    return id_string[len(prefix):]
                result[emitter_name] = [strip(row['id']) for row in q]
        return result

    def aggregate_results(self, keys, reduce=True):

        def iter_results():
            for key in keys:
                result = self.get_result(key, reduce=reduce)
                for slug, value in result.items():
                    yield slug, value

        if reduce:
            results = defaultdict(int)
            for slug, value in iter_results():
                results[slug] += value
        else:
            results = defaultdict(set)
            for slug, value in iter_results():
                results[slug].update(value)

        return results


class IndicatorDocumentMeta(schema.DocumentMeta):

    def __new__(mcs, name, bases, attrs):
        calculators = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Calculator):
                calculators[attr_name] = attr_value
                attrs[attr_name] = schema.DictProperty()
        cls = super(IndicatorDocumentMeta, mcs).__new__(mcs, name, bases, attrs)
        for slug, calculator in calculators.items():
            calculator.fluff = cls
            calculator.slug = slug
        cls._calculators = calculators
        return cls


class IndicatorDocument(schema.Document):

    __metaclass__ = IndicatorDocumentMeta
    base_doc = 'IndicatorDocument'

    document_class = None
    group_by = ()

    @classmethod
    def get_now(cls):
        return datetime.datetime.utcnow().date()

    def calculate(self, item):
        for attr, calculator in self._calculators.items():
            self[attr] = calculator.calculate(item)
        self.id = item.get_id
        for attr in self.group_by:
            self[attr] = item[attr]
        # overwrite whatever's in group_by with the default
        self['group_by'] = type(self)().group_by

    def diff(self, other_doc):
        """
        Get the diff between two IndicatorDocuments. Assumes that the documents are of the same type and that
        both have the same set of calculators and emitters. Doesn't support changes to group_by values.

        Return value is None for no diff or a dict with all indicator values
        that are different (added / removed / changed):
            {
                domains: ['domain1', 'domain2']
                database: 'db1',
                doc_type: 'MyIndicators',
                group_names: ['domain', 'owner_id'],
                group_values: ['test', 'abc']
                indicator_changes: [
                    {
                    calculator: 'visit_week',
                    emitter: 'all_visits',
                    emitter_type: 'date',
                    reduce_type: 'count',
                    values: [['2012-09-23', 1], ['2012-09-24', 1]]
                    },
                    {
                    calculator: 'visit_week',
                    emitter: 'visit_hour',
                    emitter_type: 'date',
                    reduce_type: 'sum',
                    values: [['2012-09-23', 8], ['2012-09-24', 11]]
                    },
                ]
            }
        """
        diff_keys = {}
        for calc_name in self._calculators.keys():
            if other_doc:
                calc_diff = self._shallow_dict_diff(self[calc_name], other_doc[calc_name])
                if calc_diff:
                    diff_keys[calc_name] = calc_diff
            else:
                for emitter_name, values in self[calc_name].items():
                    if values:
                        emitters = diff_keys.setdefault(calc_name, [])
                        emitters.append(emitter_name)

        if not diff_keys:
            return None

        diff = dict(domains=list(self.domains),
                    database=self.Meta.app_label,
                    doc_type=self._doc_type,
                    group_names=list(self.group_by),
                    group_values=[self[calc_name] for calc_name in self.group_by],
                    indicator_changes=[])
        indicators = diff["indicator_changes"]

        for calc_name, emitter_names in diff_keys.items():
            indicators.extend(self._indicator_diff(calc_name, emitter_names, other_doc))

        return diff

    def _indicator_diff(self, calc_name, emitter_names, other_doc):
        indicators = []
        for emitter_name in emitter_names:
            emitter = getattr(self._calculators[calc_name], emitter_name)
            emitter_type = emitter._fluff_emitter
            reduce_type = emitter._reduce_type

            if other_doc:
                self_values = set([tuple(v) for v in self[calc_name][emitter_name]])
                other_values = set([tuple(v) for v in other_doc[calc_name][emitter_name]])
                values_diff = [list(v) for v in list(self_values - other_values)]
            else:
                values_diff = self[calc_name][emitter_name]

            indicators.append(dict(calculator=calc_name,
                                   emitter=emitter_name,
                                   emitter_type=emitter_type,
                                   reduce_type=reduce_type,
                                   values=values_diff))
        return indicators

    def _shallow_dict_diff(self, left, right):
        if not left and not right:
            return None
        elif not left or not right:
            return left.keys() if left else right.keys()

        left_set, right_set = set(left.keys()), set(right.keys())
        intersect = right_set.intersection(left_set)

        added = right_set - intersect
        removed = left_set - intersect
        changed = set(o for o in intersect if left[o] != right[o])
        return added | removed | changed

    @classmethod
    def pillow(cls):
        doc_type = cls.document_class._doc_type
        domains = ' '.join(cls.domains)
        return type(FluffPillow)(cls.__name__ + 'Pillow', (FluffPillow,), {
            'couch_filter': 'fluff_filter/domain_type',
            'extra_args': {
                'domains': domains,
                'doc_type': doc_type
            },
            'document_class': cls.document_class,
            'indicator_class': cls,
        })

    @classmethod
    def has_calculator(cls, calc_name):
        return calc_name in cls._calculators

    @classmethod
    def get_calculator(cls, calc_name):
        return cls._calculators[calc_name]

    @classmethod
    def get_result(cls, calc_name, key, reduce=True):
        calculator = cls.get_calculator(calc_name)
        return calculator.get_result(key, reduce=reduce)

    @classmethod
    def aggregate_results(cls, calc_name, keys, reduce=True):
        calculator = cls.get_calculator(calc_name)
        return calculator.aggregate_results(keys, reduce=reduce)

    class Meta:
        app_label = 'fluff'


class FluffPillow(BasicPillow):
    indicator_class = IndicatorDocument

    def change_transform(self, doc_dict):
        doc = self.document_class.wrap(doc_dict)
        doc = ReadOnlyObject(doc)
        indicator_id = '%s-%s' % (self.indicator_class.__name__, doc.get_id)

        try:
            current_indicator = self.indicator_class.get(indicator_id)
        except ResourceNotFound:
            current_indicator = None

        if not current_indicator:
            indicator = self.indicator_class(_id=indicator_id)
        else:
            indicator = current_indicator
            current_indicator = indicator.to_json()
        indicator.calculate(doc)
        return current_indicator, indicator

    def change_transport(self, indicators):
        old_indicator, new_indicator = indicators
        new_indicator.save()

        diff = new_indicator.diff(old_indicator)
        if diff:
            indicator_document_updated.send(sender=self, diff=diff)
