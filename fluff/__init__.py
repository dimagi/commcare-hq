from couchdbkit.ext.django import schema
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

    domain = schema.StringProperty()
    document_class = None

    def calculate(self, item):
        for attr, calculator in self._calculators.items():
            self[attr] = calculator.calculate(item)

    @classmethod
    def pillow(cls):
        return BasicPillow.__metaclass__(cls.__name__ + 'Pillow', [BasicPillow], {
            'filter': 'fluff/global',
            'extra_args': {
                'domain': cls.domain,
                'doc_type': cls.document_class.doc_type
            },
        })
