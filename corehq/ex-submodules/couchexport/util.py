import datetime
import functools
import re
from decimal import Decimal
from inspect import isfunction
import json

import dateutil
from openpyxl.styles import numbers

from corehq.apps.export.const import MISSING_VALUE, EMPTY_VALUE
from dimagi.ext.couchdbkit import Property
from dimagi.utils.modules import to_function
from dimagi.utils.web import json_handler

_dirty_chars = re.compile(
    '[\x00-\x08\x0b-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufdd0-\ufddf\ufffe-\uffff]'
)


def force_tag_to_list(export_tag):
    if isinstance(export_tag, str):
        export_tag = [export_tag]
    assert isinstance(export_tag, list)
    return export_tag


def intersect_functions(*functions):
    functions = [fn for fn in functions if fn]
    if functions:
        def function(*args, **kwargs):
            val = True
            for fn in functions:
                val = fn(*args, **kwargs)
                if not val:
                    return val
            return val
    else:
        function = None
    return function

# deprecated
intersect_filters = intersect_functions


def clear_attachments(schema_or_doc):
    for noisy_property in ('_attachments', 'external_blobs', 'case_attachments'):
        if schema_or_doc and noisy_property in schema_or_doc:
            del schema_or_doc[noisy_property]

    if schema_or_doc:
        for action in schema_or_doc.get('actions', []):
            if 'attachments' in action and 'updated_unknown_properties' in action:
                del action['attachments']
    return schema_or_doc


def clear_computed(schema_or_doc):
    # todo: this is a hack that is coupled to commcare hq's use of the computed_
    # property exploding this namespace. however a cleaner fix in CommCare HQ would
    # be a larger effort, so it is done here.
    if schema_or_doc and 'computed_' in schema_or_doc:
        del schema_or_doc['computed_']
    return schema_or_doc


def default_cleanup(schema_or_doc):
    return clear_attachments(clear_computed(schema_or_doc))


class SerializableFunction(object):

    def __init__(self, function=None, **kwargs):
        self.functions = []
        if function:
            self.add(function, **kwargs)

    def add(self, function, **kwargs):
        self.functions.append((function, kwargs))

    def __iand__(self, other):
        self.functions.extend(other.functions)
        return self

    def __and__(self, other):
        if other is None:
            other = SerializableFunction()
        if isfunction(other):
            other = SerializableFunction(other)
        f = SerializableFunction()
        f &= self
        f &= other
        return f

    def __call__(self, *args, **kwargs):
        if self.functions:
            return intersect_functions(*[
                functools.partial(f, **f_kwargs)
                for (f, f_kwargs) in self.functions
            ])(*args, **kwargs)
        else:
            return True

    def dumps_simple(self):
        (f, kwargs), = self.functions
        assert not kwargs
        return self.to_path(f)

    def dumps(self):
        try:
            return self.dumps_simple()
        except Exception:
            pass
        functions = []
        for f, kwargs in self.functions:
            for key in kwargs:
                try:
                    kwargs[key] = kwargs[key].to_dict()
                except (AttributeError, TypeError):
                    pass
            functions.append({
                'function': self.to_path(f),
                'kwargs': kwargs
            })

        def handler(obj):
            try:
                json_handler(obj)
            except Exception:
                if isinstance(obj, SerializableFunction):
                    return {'type': 'SerializedFunction', 'dump': obj.dumps()}
                elif isfunction(obj):
                    return {'type': 'SerializedFunction', 'dump': SerializableFunction(obj).dumps()}
        return json.dumps(functions, default=handler)

    @classmethod
    def loads(cls, data):
        def object_hook(d):
            if d.get('type') == 'SerializedFunction':
                return cls.loads(d['dump'])
            else:
                return d
        try:
            functions = json.loads(data, object_hook=object_hook)
        except Exception:
            # then it's just a simple path
            return cls(to_function(data))
        self = cls()
        for o in functions:
            f, kwargs = o['function'], o['kwargs']
            f = to_function(f)
            self.add(f, **kwargs)
        return self

    @classmethod
    def to_path(cls, f):
        if isinstance(f, SerializableFunction):
            f.dumps_simple()
        else:
            return '%s.%s' % (f.__module__, f.__name__)


class SerializableFunctionProperty(Property):

    def __init__(self, verbose_name=None, name=None,
                 default='', required=False, validators=None,
                 choices=None):
        super(SerializableFunctionProperty, self).__init__(
            verbose_name=verbose_name, name=name,
            default=default, required=required, validators=validators,
            choices=choices
        )

    def to_python(self, value):
        if not value:
            return SerializableFunction()
        try:
            return SerializableFunction.loads(value)
        except ValueError:
            return SerializableFunction(to_function(value))

    def to_json(self, value):
        if isfunction(value):
            function = SerializableFunction(value)
        elif not value:
            function = SerializableFunction()
        else:
            function = value
        return function.dumps()


def get_excel_format_value(value):
    from corehq.apps.export.models.new import ExcelFormatValue

    if isinstance(value, bool):
        return ExcelFormatValue(numbers.FORMAT_GENERAL, value)
    if isinstance(value, int):
        return ExcelFormatValue(numbers.FORMAT_NUMBER, value)
    if isinstance(value, float):
        return ExcelFormatValue(numbers.FORMAT_NUMBER_00, value)
    if isinstance(value, Decimal):
        return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value))
    if isinstance(value, datetime.datetime):
        return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME, value)
    if isinstance(value, datetime.date):
        return ExcelFormatValue(numbers.FORMAT_DATE_YYYYMMDD2, value)
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    elif value is None:
        return ExcelFormatValue(numbers.FORMAT_TEXT, EMPTY_VALUE)

    if value == MISSING_VALUE or value == EMPTY_VALUE:
        return ExcelFormatValue(numbers.FORMAT_TEXT, value)

    # make sure value is string and strip whitespace before applying any
    # string operations
    value = str(value).strip()

    if value.lower() in ['true', 'false']:
        return ExcelFormatValue(
            numbers.FORMAT_GENERAL, bool(value.lower() == 'true')
        )

    # potential full date of any format
    if re.search(r"^\d+(/|-|\.)\d+(/|-|\.)\d+$", value):
        try:
            # always use standard yyy-mm-dd format for excel
            date_val = dateutil.parser.parse(value)
            # Last chance at catching an errored date. If the date is invalid,
            # yet somehow passed the regex, it will fail at this line with a
            # ValueError:
            date_val.isoformat()
            return ExcelFormatValue(numbers.FORMAT_DATE_YYYYMMDD2, date_val)
        except (ValueError, OverflowError):
            pass

    # potential time of any format
    if re.search(r"^((\d+(:))+)\d+(\.\d+((-+)((\d+(:))*)\d+)?)?(( )*[ap]m)?$",
                 value.lower()):
        try:
            # we are not returning this as a datetime object, otherwise
            # it will try to attach today's date to the value and also
            # strip the timezone information from the end
            return ExcelFormatValue(numbers.FORMAT_DATE_TIME4, value)
        except (ValueError, OverflowError):
            pass

    # potential datetime format
    if re.match(r"^\d+(/|-|\.)\d+(/|-|\.)\d+ "
                r"((\d+(:))+)\d+(\.\d+((-+)((\d+(:))*)\d+)?)?(( )*[ap]m)?$",
                value.lower()):
        try:
            # always use standard yyy-mm-dd h:mm:ss format for excel
            return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME, dateutil.parser.parse(value))
        except (ValueError, OverflowError):
            pass

    # datetime ISO format (couch datetimes)
    if re.match(r"^\d{4}(-)\d{2}(-)\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$", value):
        try:
            # always use standard yyy-mm-dd h:mm:ss format for excel
            return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME,
                                    dateutil.parser.parse(value))
        except (ValueError, OverflowError):
            pass

    # integer
    if re.match(r"^[+-]?\d+$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER, int(value))
        except OverflowError:
            return ExcelFormatValue(numbers.FORMAT_GENERAL, value)
        except ValueError:
            pass

    # decimal, US-style
    if re.match(r"^[+-]?\d+(\.)\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value))
        except ValueError:
            pass

    # decimal, EURO-style
    if re.match(r"^[+-]?\d+(,)\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value.replace(',', '.')))
        except (ValueError, OverflowError):
            pass

    # percentage without decimals
    if re.match(r"^[+-]?\d+%$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_PERCENTAGE,
                                    float(int(value.replace('%', '')) / 100))
        except (ValueError, OverflowError):
            pass

    # percentage with decimals
    if re.match(r"^[+-]?\d+(\.)\d*%$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_PERCENTAGE_00,
                                    float(float(value.replace('%', '')) / 100))
        except (ValueError, OverflowError):
            pass

    # comma-separated US-style '#,##0.00' (regexlib.com)
    if re.match(r"^(\d|-)?(\d|,)*\.?\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_COMMA_SEPARATED1,
                                    float(value.replace(',', '')))
        except (ValueError, OverflowError):
            pass

    # decimal-separated Euro-style '#.##0,00' (regexlib.com
    if re.match(r"^(\d|-)?(\d|\.)*,?\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_COMMA_SEPARATED2,
                                    float(value.replace('.', '').replace(',', '.')))
        except (ValueError, OverflowError):
            pass

    # USD with leading zeros (regexlib.com)
    if re.match(r"^(-)?\$([1-9]{1}[0-9]{0,2}(\,[0-9]{3})*(\.\d*)?)$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_CURRENCY_USD_SIMPLE,
                                    float(value.replace(',', '').replace('$', '')))
        except (ValueError, OverflowError):
            pass

    # EURO with leading zeros (regexlib.com)
    if re.match(r"^(-)?\€([1-9]{1}[0-9]{0,2}(\.[0-9]{3})*(\,\d*)?)$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_CURRENCY_EUR_SIMPLE,
                                    float(value.replace('.', '').replace(',', '.').replace('€', '')))
        except (ValueError, OverflowError):
            pass

    # no formats matched...clean and return as text
    value = _dirty_chars.sub('?', value)
    return ExcelFormatValue(numbers.FORMAT_TEXT, value)


def get_legacy_excel_safe_value(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    elif value is not None:
        value = str(value)
    else:
        value = ''
    return _dirty_chars.sub('?', value)
