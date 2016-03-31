from django.test.testcases import SimpleTestCase

from custom.ilsgateway.tanzania.handlers.soh import parse_report


class TestParseReport(SimpleTestCase):

    def test_simple_example(self):
        self.assertListEqual(parse_report('zi 10 co 20 la 30'), [('zi', 10), ('co', 20), ('la', 30)])

    def test_handling_whitespaces(self):
        self.assertListEqual(parse_report('zi10 co20 la30'), [('zi', 10), ('co', 20), ('la', 30)])

    def test_handling_zeros(self):
        self.assertListEqual(parse_report('zi1O co2O la3O'), [('zi', 10), ('co', 20), ('la', 30)])

    def test_handling_extra_spam(self):
        self.assertListEqual(
            parse_report('randomextradata zi1O co2O la3O randomextradata'),
            [('zi', 10), ('co', 20), ('la', 30)]
        )

    def test_handling_minus_sign(self):
        self.assertListEqual(parse_report('zi -1O co +2O la -3O'), [('zi', -10), ('co', 20), ('la', -30)])

    def test_handling_minus_with_whitespaces(self):
        self.assertListEqual(parse_report('zi -1O co +  2O la -  3O'), [('zi', -10), ('co', 20), ('la', -30)])
