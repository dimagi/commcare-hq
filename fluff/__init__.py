from couchdbkit import ResourceNotFound
from couchdbkit.ext.django import schema
import datetime
from dimagi.utils.parsing import json_format_date
from pillowtop.listener import BasicPillow


def date_emitter(fn):
    fn._fluff_emitter = 'date'
    return fn


def null_emitter(fn):
    fn._fluff_emitter = 'null'
    return fn


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
            values[slug] = (
                list(getattr(self, slug)(item))
                if passes_filter else []
            )
        return values

    def get_result(self, key, reduce=True):
        return self.fluff.get_result(self.slug, key, reduce=reduce)


class IndicatorDocumentMeta(schema.DocumentMeta):

    def __new__(mcs, name, bases, attrs):
        calculators = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Calculator):
                calculators[attr_name] = attr_value
                attrs[attr_name] = schema.DictProperty()
        cls = super(IndicatorDocumentMeta, mcs).__new__(mcs, name, bases, attrs)
        if not hasattr(cls, '_calculators'):
            cls._calculators = {}
        cls._calculators.update(calculators)
        for slug, calculator in cls._calculators.items():
            calculator.fluff = cls
            calculator.slug = slug
        return cls


class IndicatorDocument(schema.Document):

    __metaclass__ = IndicatorDocumentMeta
    base_doc = 'IndicatorDocument'

    document_class = None
    group_by = ()

    def calculate(self, item):
        for attr, calculator in self._calculators.items():
            self[attr] = calculator.calculate(item)
        self.id = item.get_id
        for attr in self.group_by:
            self[attr] = item[attr]
        # overwrite whatever's in group_by with the default
        self['group_by'] = type(self)().group_by

    @classmethod
    def pillow(cls):
        doc_type = cls.document_class._doc_type
        domains = ' '.join(cls.domains)
        return type(FluffPillow)(cls.__name__ + 'Pillow', (FluffPillow,), {
            'couch_filter': 'fluff/domain_type',
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
        result = {}
        for emitter_name in calculator._fluff_emitters:
            shared_key = [cls._doc_type] + key + [calc_name, emitter_name]
            emitter_type = getattr(calculator, emitter_name)._fluff_emitter
            q_args = {
                'reduce': reduce,
                'include_docs': not reduce,
            }
            if emitter_type == 'date':
                now = datetime.datetime.utcnow().date()
                start = now - calculator.window
                end = now
                q = cls.view(
                    'fluff/generic',
                    startkey=shared_key + [json_format_date(start)],
                    endkey=shared_key + [json_format_date(end)],
                    **q_args
                ).all()
            elif emitter_type == 'null':
                q = cls.view(
                    'fluff/generic',
                    key=shared_key + [None],
                    **q_args
                ).all()
            if reduce:
                try:
                    result[emitter_name] = q[0]['value']
                except IndexError:
                    result[emitter_name] = 0
            else:
                result[emitter_name] = q
        return result

    class Meta:
        app_label = 'fluff'


class FluffPillow(BasicPillow):
    indicator_class = IndicatorDocument

    def change_transform(self, doc_dict):
        doc = self.document_class.wrap(doc_dict)
        indicator_id = '%s-%s' % (self.indicator_class.__name__, doc.get_id)

        try:
            indicator = self.indicator_class.get(indicator_id)
        except ResourceNotFound:
            indicator = self.indicator_class(_id=indicator_id)
        indicator.calculate(doc)
        return indicator

    def change_transport(self, indicator):
        indicator.save()
