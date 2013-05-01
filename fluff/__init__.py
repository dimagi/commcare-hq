from couchdbkit import ResourceNotFound, StringProperty
from couchdbkit.ext.django import schema
import datetime
from dimagi.utils.parsing import json_format_datetime
from pillowtop.listener import BasicPillow


def emitter(fn):
    fn._emitter = True
    return fn


class CalculatorMeta(type):
    def __new__(mcs, name, bases, attrs):
        emitters = []
        for attr in attrs:
            if getattr(attrs[attr], '_emitter', None):
                emitters.append(attr)
        cls = super(CalculatorMeta, mcs).__new__(mcs, name, bases, attrs)
        cls._emitters = emitters
        return cls


class Calculator(object):
    __metaclass__ = CalculatorMeta

    def __init__(self, window):
        self.window = window

    def filter(self, item):
        return True

    def to_python(self, value):
        return value

    def calculate(self, item):
        passes_filter = self.filter(item)
        values = {}
        for slug in self._emitters:
            values[slug] = (list(getattr(self, slug)(item))
                if passes_filter else [])
        return values


class IndicatorDocumentMeta(schema.DocumentMeta):

    def __new__(mcs, name, bases, attrs):
        calculators = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Calculator):
                calculators[attr_name] = attr_value
                attrs[attr_name] = schema.DictProperty()
        cls = super(IndicatorDocumentMeta, mcs).__new__(mcs, name, bases, attrs)
        cls._calculators = calculators
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
    def get_result(cls, calc_name, key):
        calculator = cls._calculators[calc_name]
        result = {}
        for emitter_name in calculator._emitters:
            shared_key = [cls._doc_type] + key + [calc_name, emitter_name]
            now = datetime.datetime.utcnow()
            q = cls.get_db().view(
                'fluff/generic',
                startkey=shared_key + [json_format_datetime(now - calculator.window)],
                endkey=shared_key + [json_format_datetime(now)],
            ).all()
            try:
                result[emitter_name] = q[0]['value']
            except IndexError:
                result[emitter_name] = None
        return result

    class Meta:
        app_label = ''


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
