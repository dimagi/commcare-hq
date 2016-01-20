from couchdbkit.ext.django import schema
import datetime
import sqlalchemy
from .util import get_indicator_model, default_null_value_placeholder
from .calculators import Calculator
from .const import ALL_TYPES, TYPE_STRING


class FlatField(schema.StringProperty):
    """
    This constructs a field for your indicator document that can perform basic
    operations on an item.  Pass in a function that accepts an item and returns
    a string.  This field is not a calculator, so it cannot be accessed with
    get_results (yet).  Instead, access the fluff doc directly.
    Example:

        class MyFluff(fluff.IndicatorDocument):
            document_class = CommCareCase
            ...
            name = fluff.FlatField(lambda case: case.name)
    """

    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        super(FlatField, self).__init__(*args, **kwargs)

    def calculate(self, item):
        result = self.fn(item)
        assert isinstance(result, basestring)
        return result


class AttributeGetter(object):
    """
    If you need to do something fancy in your group_by you would use this.
    """
    def __init__(self, attribute, getter_function=None):
        """
        attribute is what the attribute is set as in the fluff indicator doc.
        getter_function is how to get it out of the source doc.
        if getter_function isn't specified it will use source[attribute] as
        the getter.
        """
        self.attribute = attribute
        if getter_function is None:
            getter_function = lambda item: getattr(item, attribute)

        self.getter_function = getter_function


class IndicatorDocumentMeta(schema.DocumentMeta):

    def __new__(mcs, name, bases, attrs):
        calculators = {}
        flat_fields = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Calculator):
                calculators[attr_name] = attr_value
                attrs[attr_name] = schema.DictProperty()
            if isinstance(attr_value, FlatField):
                flat_fields[attr_name] = attr_value
        cls = super(IndicatorDocumentMeta, mcs).__new__(mcs, name, bases, attrs)
        for slug, calculator in calculators.items():
            calculator.fluff = cls
            calculator.slug = slug
        cls._calculators = calculators
        cls._flat_fields = flat_fields

        instance = cls()
        if instance.save_direct_to_sql:
            cls._table = get_indicator_model(name, instance)
        return cls


class IndicatorDocument(schema.Document):

    __metaclass__ = IndicatorDocumentMeta
    base_doc = 'IndicatorDocument'

    document_class = None
    wrapper = None
    document_filter = None
    group_by = ()
    save_direct_to_sql = None
    kafka_topic = None  # if set, this will use a kafka feed instead of couch for the pillow

    # A list of doc types to delete from fluff (in case a previously matching document no
    # longer is relevant)
    # eg, doc_type = XFormInstance
    # deleted_types = ('XFormArchived', 'XFormDuplicate', 'XFormDeprecated', 'XFormError')
    deleted_types = ()

    # Mapping of group_by field to type. Used to communicate expected type in fluff diffs.
    # See ALL_TYPES
    group_by_type_map = None

    @property
    def wrapped_group_by(self):
        def _wrap_if_necessary(string_or_attribute_getter):
            if isinstance(string_or_attribute_getter, basestring):
                getter = AttributeGetter(string_or_attribute_getter)
            else:
                getter = string_or_attribute_getter
            assert isinstance(getter, AttributeGetter)
            return getter

        return (_wrap_if_necessary(item) for item in type(self)().group_by)

    def get_group_names(self):
        return [gb.attribute for gb in self.wrapped_group_by]

    def get_group_values(self):
        return [self[attr] for attr in self.get_group_names()]

    def get_group_types(self):
        group_by_type_map = self.group_by_type_map or {}
        for gb in self.wrapped_group_by:
            attrib = gb.attribute
            if attrib not in group_by_type_map:
                group_by_type_map[attrib] = TYPE_STRING
            else:
                assert group_by_type_map[attrib] in ALL_TYPES

        return group_by_type_map

    @classmethod
    def get_now(cls):
        return datetime.datetime.utcnow().date()

    def update(self, item):
        for attr, field in self._flat_fields.items():
            self[attr] = field.calculate(item)

    def calculate(self, item):
        for attr, calculator in self._calculators.items():
            self[attr] = calculator.calculate(item)
        self.id = item.get_id
        for getter in self.wrapped_group_by:
            self[getter.attribute] = getter.getter_function(item)
        # overwrite whatever's in group_by with the default
        self._doc['group_by'] = list(self.get_group_names())
        self.update(item)

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
                    values: [
                        {'date': '2012-09-23', 'value': 1, 'group_by': None},
                        {'date': '2012-09-24', 'value': 1, 'group_by': None}
                    ]},
                    {
                    calculator: 'visit_week',
                    emitter: 'visit_hour',
                    emitter_type: 'date',
                    reduce_type: 'sum',
                    values: [
                        {'date': '2012-09-23', 'value': 8, 'group_by': None},
                        {'date': '2012-09-24', 'value': 11, 'group_by': None}
                    ]},
                ],
                all_indicators: [
                    {
                    calculator: 'visit_week',
                    emitter: 'visit_hour',
                    emitter_type: 'date',
                    reduce_type: 'sum'
                    },
                    ....
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
                    group_names=self.get_group_names(),
                    group_values=self.get_group_values(),
                    group_type_map=self.get_group_types(),
                    indicator_changes=[],
                    all_indicators=[])
        indicator_changes = diff["indicator_changes"]
        all_indicators = diff["all_indicators"]

        for calc_name, emitter_names in diff_keys.items():
            indicator_changes.extend(self._indicator_diff(calc_name, emitter_names, other_doc))

        for calc_name in self._calculators.keys():
            for emitter_name in self[calc_name].keys():
                all_indicators.append(self._indicator_meta(calc_name, emitter_name))

        return diff

    def _indicator_meta(self, calc_name, emitter_name, values=None):
        emitter = getattr(self._calculators[calc_name], emitter_name)
        emitter_type = emitter._fluff_emitter
        reduce_type = emitter._reduce_type
        meta = dict(calculator=calc_name,
           emitter=emitter_name,
           emitter_type=emitter_type,
           reduce_type=reduce_type
        )

        if values is not None:
            meta['values'] = values

        return meta

    def _indicator_diff(self, calc_name, emitter_names, other_doc):
        indicators = []
        for emitter_name in emitter_names:
            class NormalizedEmittedValue(object):
                """Normalize the values to the dictionary form to allow comparison"""
                def __init__(self, value):
                    if isinstance(value, dict):
                        self.value = value
                    elif isinstance(value, list):
                        self.value = dict(date=value[0], value=value[1], group_by=None)

                    if self.value['date'] and not isinstance(self.value['date'], datetime.date):
                        self.value['date'] = datetime.datetime.strptime(self.value['date'], '%Y-%m-%d').date()

                def __key(self):
                    gb = self.value['group_by']
                    return self.value['date'], self.value['value'], tuple(gb) if gb else None

                def __eq__(x, y):
                    return x.__key() == y.__key()

                def __hash__(self):
                    return hash(self.__key())

                def __repr__(self):
                    return str(self.value)

            if other_doc:
                self_values = set([NormalizedEmittedValue(v) for v in self[calc_name][emitter_name]])
                try:
                    _vals = other_doc[calc_name][emitter_name]
                except KeyError:
                    _vals = ()
                other_values = set([NormalizedEmittedValue(v) for v in _vals])
                values_diff = [v for v in list(self_values - other_values)]
            else:
                values_diff = [NormalizedEmittedValue(v) for v in self[calc_name][emitter_name]]

            values = [v.value for v in values_diff]
            indicators.append(self._indicator_meta(calc_name, emitter_name, values=values))
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

    def save_to_sql(self, diff, engine):
        if not diff:
            # empty indicator document
            return

        default_key = (self.id,) + tuple(diff['group_values'])
        rows = {}

        def set_row_val(rowkey, col_name, col_value):
            row = rows.setdefault(rowkey, {})
            row[col_name] = col_value

        flat_keys = None
        try:
            flat_keys = self._flat_fields.keys()
        except AttributeError:
            pass

        for change in diff['indicator_changes']:
            name = '{0}_{1}'.format(change['calculator'], change['emitter'])
            for value_dict in change['values']:
                value = value_dict['value']
                group_by = value_dict['group_by']
                date = value_dict['date']
                if group_by:
                    key = (self.id,) + tuple(group_by) + (date,)
                else:
                    key = default_key + (date,)
                set_row_val(key, name, value)
                for flat_key in flat_keys:
                    set_row_val(key, flat_key, self[flat_key])

        types = self.get_group_types()
        types['date'] = 'date'
        names = ['doc_id'] + self.get_group_names() + ['date']
        connection = engine.connect()
        try:
            # delete all existing rows for this doc to ensure we aren't left with stale data
            delete = self._table.delete(self._table.c.doc_id == self.id)
            connection.execute(delete)

            for key, columns in rows.items():
                key_columns = dict(zip(names, key))
                for name, value in key_columns.items():
                    if value is None:
                        key_columns[name] = default_null_value_placeholder(types[name])
                all_columns = dict(key_columns.items() + columns.items())

                try:
                    insert = self._table.insert().values(**all_columns)
                    connection.execute(insert)
                except sqlalchemy.exc.IntegrityError:
                    if columns:
                        update = self._table.update().values(**columns)
                        for k, v in key_columns.items():
                            update = update.where(self._table.c[k] == v)
                        connection.execute(update)
        finally:
            connection.close()

    def delete_from_sql(self, engine):
        delete = self._table.delete(self._table.c.doc_id == self.id)
        engine.execute(delete)

    @classmethod
    def pillow(cls):
        from .pillow import FluffPillow
        wrapper = cls.wrapper or cls.document_class
        doc_type = cls.document_class._doc_type
        extra_args = dict(doc_type=doc_type)
        if cls.domains:
            domains = ' '.join(cls.domains)
            extra_args['domains'] = domains

        return type(FluffPillow)(cls.__name__ + 'Pillow', (FluffPillow,), {
            'extra_args': extra_args,
            'document_class': cls.document_class,
            'wrapper': wrapper,
            'indicator_class': cls,
            'document_filter': cls.document_filter,
            'domains': cls.domains,
            'doc_type': doc_type,
            'save_direct_to_sql': cls().save_direct_to_sql,
            'deleted_types': cls.deleted_types,
            'kafka_topic': cls().kafka_topic,
        })

    @classmethod
    def has_calculator(cls, calc_name):
        return calc_name in cls._calculators

    @classmethod
    def get_calculator(cls, calc_name):
        return cls._calculators[calc_name]

    @classmethod
    def get_result(cls, calc_name, key, date_range=None, reduce=True):
        calculator = cls.get_calculator(calc_name)
        return calculator.get_result(key, date_range=date_range, reduce=reduce)

    @classmethod
    def aggregate_results(cls, calc_name, keys, reduce=True, date_range=None):
        calculator = cls.get_calculator(calc_name)
        return calculator.aggregate_results(keys, reduce=reduce, date_range=date_range)

    @classmethod
    def aggregate_all_results(cls, keys, reduce=True, date_range=None):
        return dict(
            (calc_name, calc.aggregate_results(keys, reduce=reduce, date_range=date_range))
            for calc_name, calc in cls._calculators.items()
        )

    class Meta:
        app_label = 'fluff'
