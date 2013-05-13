from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)

from unittest2 import TestCase
import fluff
from couchdbkit import Document, DocumentSchema, DocumentBase
from datetime import date
from fakecouch import FakeCouchDb


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


class Test(TestCase):
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

    def test_indicator_calculation(self):
        pillow = MockIndicators.pillow()()
        pillow.processor({'changes': [], 'id': '123', 'seq': 1})
        indicator = fakedb.mock_docs.get("MockIndicators-123", None)
        self.assertIsNotNone(indicator)
        self.assertIn("visits_week", indicator)
        self.assertIn("all_visits", indicator["visits_week"])
        self.assertEqual("2012-09-23", indicator["visits_week"]["all_visits"][0])
        self.assertEqual("2012-09-24", indicator["visits_week"]["all_visits"][1])
        self.assertIsNone(indicator["visits_week"]["null_emitter"][0])

    def test_indicator_diff_new(self):
        doc = MockIndicators(domain="mock",
                             owner_id="123",
                             visits_week=dict(all_visits=[date(2012, 02, 23)],
                                              null_emitter=[]))
        diff = doc.diff(None)
        expected = dict(database=MockIndicators.Meta.app_label,
                        doc_type='MockIndicators',
                        group_values=['mock', '123'],
                        group_names=['domain', 'owner_id'],
                        indicator_changes=[
                            dict(calculator='visits_week',
                                 emitter='all_visits',
                                 emitter_type='date',
                                 values=[date(2012, 2, 23)])
                        ])
        self.assertEqual(expected, diff)

    def test_indicator_diff_same(self):
        doc = MockIndicators(domain="mock",
                             owner_id="123",
                             visits_week=dict(all_visits=[date(2012, 02, 23)],
                                              null_emitter=[]))
        another = doc.clone()
        diff = doc.diff(another)
        self.assertIsNone(diff)

    def test_indicator_diff(self):
        current = MockIndicators(domain="mock",
                                 owner_id="123",
                                 visits_week=dict(all_visits=[date(2012, 02, 23)],
                                                  null_emitter=[]))
        new = MockIndicators(domain="mock",
                             owner_id="123",
                             visits_week=dict(all_visits=[date(2012, 02, 24)],
                                              null_emitter=[None]))

        diff = new.diff(current)
        self.assertIsNotNone(diff)
        self.maxDiff = None
        expected = dict(database=MockIndicators.Meta.app_label,
                        doc_type='MockIndicators',
                        group_values=['mock', '123'],
                        group_names=['domain', 'owner_id'],
                        indicator_changes=[
                            dict(calculator='visits_week',
                                 emitter='null_emitter',
                                 emitter_type='null',
                                 values=[None]),
                            dict(calculator='visits_week',
                                 emitter='all_visits',
                                 emitter_type='date',
                                 values=[date(2012, 2, 24)])
                        ])
        self.assertEqual(expected, diff)


fakedb = FakeCouchDb(docs={"123": dict(actions=[dict(date="2012-09-23"), dict(date="2012-09-24")],
                                       get_id="123",
                                       domain="mock",
                                       owner_id="test_owner")})

DocumentSchema._db = fakedb
DocumentBase._db = fakedb


class MockDoc(Document):
    _doc_type = "Mock"


class VisitCalculator(fluff.Calculator):
    @fluff.date_emitter
    def all_visits(self, case):
        for action in case.actions:
            yield action['date']

    @fluff.null_emitter
    def null_emitter(self, case):
        yield None


class MockIndicators(fluff.IndicatorDocument):
    from datetime import timedelta

    document_class = MockDoc
    group_by = ('domain', 'owner_id')
    domains = ('test',)

    visits_week = VisitCalculator(window=timedelta(days=7))

    class Meta:
        app_label = 'Mock'
