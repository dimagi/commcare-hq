# encoding: utf-8
import datetime
from decimal import Decimal
from django.test import SimpleTestCase
from dimagi.utils.web import json_handler


class JsonHandlerTest(SimpleTestCase):

    def test_date(self):
        self.assertEqual('2014-01-05', json_handler(datetime.date(2014, 1, 5)))

    def test_datetime(self):
        self.assertEqual('2014-01-05T12:15:05.000000Z', json_handler(datetime.datetime(2014, 1, 5, 12, 15, 5)))

    def test_time(self):
        self.assertEqual('11:15:22', json_handler(datetime.time(11, 15, 22)))

    def test_time_24_hour(self):
        self.assertEqual('23:15:22', json_handler(datetime.time(23, 15, 22)))

    def test_decimal(self):
        self.assertEqual(3.14, json_handler(Decimal('3.14')))

    def test_to_json(self):
        json_rep = 'json rep'
        class Klass(object):
            def to_json(self):
                return json_rep
        self.assertEqual(json_rep, json_handler(Klass()))

    def test_to_complete_json(self):
        json_rep = 'json rep'
        class Klass(object):
            def to_complete_json(self):
                return json_rep
        self.assertEqual(json_rep, json_handler(Klass()))
