from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)

import fluff
from unittest2 import TestCase
from couchdbkit import Document
from datetime import date, datetime, timedelta
from fakecouch import FakeCouchDb
from dimagi.utils.parsing import json_format_date

WEEK = timedelta(days=7)


class Base0(fluff.Calculator):
    @fluff.filter_by
    def base_0_filter(self):
        pass

    @fluff.date_emitter
    def base_0_emitter(self):
        pass


class Base1(Base0):
    @fluff.filter_by
    def base_1_filter(self):
        pass

    @fluff.date_emitter
    def base_1_emitter(self):
        pass


class Base2(Base0):
    @fluff.filter_by
    def base_2_filter(self):
        pass

    @fluff.date_emitter
    def base_2_emitter(self):
        pass


class Base3(Base1, Base2):
    @fluff.filter_by
    def base_3_filter(self):
        pass

    @fluff.date_emitter
    def base_3_emitter(self):
        pass


class Indicators1(fluff.IndicatorDocument):
    base0 = Base0(window=WEEK)


class Indicators2(fluff.IndicatorDocument):
    base1 = Base1(window=WEEK)
    base2 = Base2(window=WEEK)


class Test(TestCase):
    def setUp(self):
        self.fakedb = FakeCouchDb()
        MockIndicators.set_db(self.fakedb)
        MockIndicatorsWithGetters.set_db(self.fakedb)
        MockDoc.set_db(self.fakedb)

    def test_calculator_base_classes(self):
        # Base0
        self.assertEqual(Base0._fluff_emitters, set([
            'base_0_emitter',
        ]))
        self.assertEqual(Base0._fluff_filters, set([
            'base_0_filter',
        ]))

        # Base1
        self.assertEqual(Base1._fluff_emitters, set([
            'base_0_emitter',
            'base_1_emitter',
        ]))
        self.assertEqual(Base1._fluff_filters, set([
            'base_0_filter',
            'base_1_filter',
        ]))

        # Base2
        self.assertEqual(Base2._fluff_emitters, set([
            'base_0_emitter',
            'base_2_emitter',
        ]))
        self.assertEqual(Base2._fluff_filters, set([
            'base_0_filter',
            'base_2_filter',
        ]))

        # Base2
        self.assertEqual(Base3._fluff_emitters, set([
            'base_0_emitter',
            'base_1_emitter',
            'base_2_emitter',
            'base_3_emitter',
        ]))
        self.assertEqual(Base3._fluff_filters, set([
            'base_0_filter',
            'base_1_filter',
            'base_2_filter',
            'base_3_filter',
        ]))

    def test_indicator_classes(self):
        self.assertEquals(Indicators1._calculators.keys(), ['base0'])
        self.assertEquals(Indicators2._calculators.keys(), ['base1', 'base2'])

    def test_indicator_calculation(self):
        actions = [dict(date="2012-09-23", x=2), dict(date="2012-09-24", x=3)]
        self.fakedb.mock_docs["123"] = dict(actions=actions,
                                            get_id="123",
                                            domain="mock",
                                            owner_id="test_owner")
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            classname = cls.__name__
            pillow = cls.pillow()()
            pillow.processor({'changes': [], 'id': '123', 'seq': 1})
            indicator = self.fakedb.mock_docs.get("%s-123" % classname, None)
            self.assertIsNotNone(indicator)
            self.assertEqual(8, len(indicator))
            self.assertEqual(8, len(indicator['value_week']))
            self.assertIn("value_week", indicator)
            self.assertIn("date", indicator["value_week"])
            self.assertIn("null", indicator["value_week"])
            self.assertIn("date_value", indicator["value_week"])
            self.assertIn("null_value", indicator["value_week"])
            self.assertEqual({'date': "2012-09-23", 'value': 1, 'group_by': None}, indicator["value_week"]["date"][0])
            self.assertEqual({'date': "2012-09-24", 'value': 1, 'group_by': None}, indicator["value_week"]["date"][1])
            self.assertEqual({'date': None, 'value': 1, 'group_by': None}, indicator["value_week"]["null"][0])

            self.assertEqual({'date': "2012-09-23", 'value': 2, 'group_by': None}, indicator["value_week"]["date_value"][0])
            self.assertEqual({'date': "2012-09-24", 'value': 3, 'group_by': None}, indicator["value_week"]["date_value"][1])
            self.assertEqual({'date': None, 'value': 2, 'group_by': None}, indicator["value_week"]["null_value"][0])

            self.assertEqual(dict(date='2013-01-01', group_by=['abc', 'xyz'], value=3), indicator["value_week"]["group_list"][0])
            self.assertEqual(dict(date='2013-01-01', group_by=['abc'], value=2), indicator["value_week"]["group_val"][0])
            self.assertEqual(dict(date='2013-01-01', group_by=['abc'], value=1), indicator["value_week"]["group_no_val"][0])


    def test_calculator_calculate(self):
        calc = ValueCalculator(WEEK)
        values = calc.calculate(MockDoc.wrap(dict(actions=[dict(date="2012-09-23", x=2),
                                                           dict(date="2012-09-24", x=3)])))
        self.assertEquals(len(values.keys()), 8)
        self.assertEquals(values['null_value'], [dict(date=None, value=2, group_by=None)])
        self.assertEquals(values['date_value'], [
            dict(date=date(2012, 9, 23), value=2, group_by=None),
            dict(date=date(2012, 9, 24), value=3, group_by=None)])
        self.assertEquals(values['date'], [
            dict(date=date(2012, 9, 23), value=1, group_by=None),
            dict(date=date(2012, 9, 24), value=1, group_by=None)])
        self.assertEquals(values['null'], [dict(date=None, value=1, group_by=None)])
        self.assertEquals(values['group_list'], [dict(date=date(2013, 1, 1), group_by=['abc', 'xyz'], value=3)])
        self.assertEquals(values['group_val'], [dict(date=date(2013, 1, 1), group_by=['abc'], value=2)])
        self.assertEquals(values['group_no_val'], [dict(date=date(2013, 1, 1), group_by=['abc'], value=1)])
        self.assertEquals(values['group_null'], [dict(date=None, group_by=['abc'], value=1)])

    def test_calculator_get_result(self):
        key = ['a', 'b']
        now = datetime.utcnow().date()
        start = json_format_date(now - WEEK)
        end = json_format_date(now)
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            classname = cls.__name__
            self.fakedb.add_view('fluff/generic', [
                (
                    {'reduce': True, 'key': [classname, 'a', 'b', 'value_week', 'null', None]},
                    [{"key": None, "value": {"sum": 3}}]
                ),
                (
                    {'reduce': True, 'key': [classname, 'a', 'b', 'value_week', 'null_value', None]},
                    [{"key": None, "value": {"max": 8}}]
                ),
                (
                    {'startkey': [classname, 'a', 'b', 'value_week', 'date', start],
                        'endkey': [classname, 'a', 'b', 'value_week', 'date', end],
                        'reduce': True},
                    [{"key": None, "value": {"count": 7}}]
                ),
                (
                    {'startkey': [classname, 'a', 'b', 'value_week', 'date_value', start],
                        'endkey': [classname, 'a', 'b', 'value_week', 'date_value', end],
                        'reduce': True},
                    [{"key": None, "value": {"sum": 11}}]
                )
            ])
            value = cls.get_result('value_week', key, reduce=True)
            self.assertEqual(value['null'], 3)
            self.assertEqual(value['date'], 7)
            self.assertEqual(value['date_value'], 11)
            self.assertEqual(value['null_value'], 8)

    def test_indicator_diff_new(self):
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            classname = cls.__name__
            doc = cls(
                domain="mock",
                owner_id="123",
                value_week=dict(
                    date=[[date(2012, 02, 23), 1]],
                    null=[],
                    date_value=[],
                    null_value=[[None, 3]]
                )
            )
            diff = doc.diff(None)
            self.maxDiff = None
            expected = dict(domains=['test'],
                            database=cls.Meta.app_label,
                            doc_type=classname,
                            group_values=['mock', '123'],
                            group_names=['domain', 'owner_id'],
                            indicator_changes=[
                                dict(calculator='value_week',
                                     emitter='date',
                                     emitter_type='date',
                                     reduce_type='count',
                                     values=[dict(date=date(2012, 2, 23), value=1, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='null_value',
                                     emitter_type='null',
                                     reduce_type='max',
                                     values=[dict(date=None, value=3, group_by=None)])
                            ],
                            all_indicators=self.all_indicators())
            self.assertEqual(expected, diff)

    def test_indicator_diff_same(self):
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            doc = cls(domain="mock",
                      owner_id="123",
                      value_week=dict(
                          date=[date(2012, 02, 23)],
                          null=[],
                          date_value=[],
                          null_value=[[None, 3]]
                      ))
            another = doc.clone()
            diff = doc.diff(another)
            self.assertIsNone(diff)

    def all_indicators(self):
        return [
            dict(calculator='value_week',
                 emitter='date_value',
                 emitter_type='date',
                 reduce_type='sum'),
            dict(calculator='value_week',
                 emitter='date',
                 emitter_type='date',
                 reduce_type='count'),
            dict(calculator='value_week',
                 emitter='null',
                 emitter_type='null',
                 reduce_type='sum'),
            dict(calculator='value_week',
                 emitter='null_value',
                 emitter_type='null',
                 reduce_type='max'),
        ]

    def test_indicator_diff(self):
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            current = cls(domain="mock",
                                     owner_id="123",
                                     value_week=dict(date=[[date(2012, 02, 23), 1]],
                                                     null=[],
                                                     date_value=[[date(2012, 02, 23), 3]],
                                                     null_value=[]))
            new = cls(domain="mock",
                      owner_id="123",
                      value_week=dict(
                          date=[[date(2012, 02, 24), 1]],
                          null=[[None, 1]],
                          date_value=[[date(2012, 02, 23), 4]],
                          null_value=[[None, 2]]))

            diff = new.diff(current)
            self.assertIsNotNone(diff)
            self.maxDiff = None
            expected = dict(domains=['test'],
                            database=cls.Meta.app_label,
                            doc_type=cls.__name__,
                            group_values=['mock', '123'],
                            group_names=['domain', 'owner_id'],
                            indicator_changes=[
                                dict(calculator='value_week',
                                     emitter='date_value',
                                     emitter_type='date',
                                     reduce_type='sum',
                                     values=[dict(date=date(2012, 2, 23), value=4, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='date',
                                     emitter_type='date',
                                     reduce_type='count',
                                     values=[dict(date=date(2012, 2, 24), value=1, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='null',
                                     emitter_type='null',
                                     reduce_type='sum',
                                     values=[dict(date=None, value=1, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='null_value',
                                     emitter_type='null',
                                     reduce_type='max',
                                     values=[dict(date=None, value=2, group_by=None)])
                            ],
                            all_indicators=self.all_indicators())
            self.assertEqual(expected, diff)

    def test_indicator_diff_dict(self):
        for cls in [MockIndicators, MockIndicatorsWithGetters]:
            current = cls(domain="mock",
                                     owner_id="123",
                                     value_week=dict(
                                         date=[dict(date=date(2012, 2, 23), value=1, group_by=None)],
                                         date_value=[[date(2012, 02, 24), 1]],
                                         group_list=[],
                                         null_value=[dict(date=None, value=1, group_by='abc')],
                                     ))
            new = cls(domain="mock",
                      owner_id="123",
                      value_week=dict(
                          date=[[date(2012, 02, 24), 1]],
                          date_value=[dict(date=date(2012, 2, 20), value=2, group_by=None)],
                          group_list=[dict(date=date(2013, 1, 1), value=3, group_by=['abc', '123'])],
                          null_value=[dict(date=None, value=1, group_by='abc')],
                      ))

            diff = new.diff(current)
            self.assertIsNotNone(diff)
            self.maxDiff = None
            expected = dict(domains=['test'],
                            database=cls.Meta.app_label,
                            doc_type=cls.__name__,
                            group_values=['mock', '123'],
                            group_names=['domain', 'owner_id'],
                            indicator_changes=[
                                dict(calculator='value_week',
                                     emitter='date_value',
                                     emitter_type='date',
                                     reduce_type='sum',
                                     values=[dict(date=date(2012, 2, 20), value=2, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='date',
                                     emitter_type='date',
                                     reduce_type='count',
                                     values=[dict(date=date(2012, 2, 24), value=1, group_by=None)]),
                                dict(calculator='value_week',
                                     emitter='group_list',
                                     emitter_type='date',
                                     reduce_type='sum',
                                     values=[dict(date=date(2013, 1, 1), value=3, group_by=['abc', '123'])]),
                            ],
                            all_indicators=[
                                dict(calculator='value_week',
                                     emitter='date_value',
                                     emitter_type='date',
                                     reduce_type='sum'),
                                dict(calculator='value_week',
                                     emitter='date',
                                     emitter_type='date',
                                     reduce_type='count'),
                                dict(calculator='value_week',
                                     emitter='group_list',
                                     emitter_type='date',
                                     reduce_type='sum'),
                                dict(calculator='value_week',
                                     emitter='null_value',
                                     emitter_type='null',
                                     reduce_type='max'),
                            ])
            self.assertEqual(expected, diff)


class MockDoc(Document):
    _doc_type = "Mock"


class ValueCalculator(fluff.Calculator):
    @fluff.date_emitter
    def date_value(self, case):
        for action in case.actions:
            yield [action['date'], action['x']]

    @fluff.custom_null_emitter('max')
    def null_value(self, case):
        yield [None, 2]

    @fluff.custom_date_emitter('count')
    def date(self, case):
        for action in case.actions:
            yield action['date']

    @fluff.null_emitter
    def null(self, case):
        yield None

    @fluff.date_emitter
    def group_list(self, case):
        yield dict(date=date(2013, 1, 1), value=3, group_by=['abc', 'xyz'])

    @fluff.date_emitter
    def group_val(self, case):
        yield dict(date=date(2013, 1, 1), value=2, group_by='abc')

    @fluff.date_emitter
    def group_no_val(self, case):
        yield dict(date=date(2013, 1, 1), group_by='abc')

    @fluff.null_emitter
    def group_null(self, case):
        yield dict(group_by='abc')


class MockIndicators(fluff.IndicatorDocument):

    document_class = MockDoc
    group_by = ('domain', 'owner_id')
    domains = ('test',)

    value_week = ValueCalculator(window=WEEK)

    class Meta:
        app_label = 'Mock'


class MockIndicatorsWithGetters(fluff.IndicatorDocument):

    document_class = MockDoc
    group_by = (
        fluff.AttributeGetter('domain'),
        fluff.AttributeGetter('owner_id', getter_function=lambda item: item['owner_id'])
    )
    domains = ('test',)

    value_week = ValueCalculator(window=WEEK)

    class Meta:
        app_label = 'Mock'
