from django.test import SimpleTestCase
from corehq.apps.app_manager.xpath import XPath


class XPathTest(SimpleTestCase):

    def test_paren(self):
        xp = XPath('/data/q1')
        self.assertEqual('/data/q1', xp.paren())
        self.assertEqual('(/data/q1)', xp.paren(force=True))
        self.assertEqual('(/data/q1)', XPath('/data/q1', compound=True).paren())

    def test_slash(self):
        self.assertEqual('/data/1/2', XPath().slash('/data').slash('1').slash('2'))
        self.assertEqual('/data/1/2', XPath('/data').slash('1').slash('2'))

    def test_select(self):
        self.assertEqual("/data/1[anything]", XPath('/data/1').select_raw('anything'))
        self.assertEqual("/data/1[a='b']", XPath('/data/1').select('a', 'b'))
        self.assertEqual("/data/1[a=/data/b]", XPath('/data/1').select('a', XPath('/data/b')))

    def test_count(self):
        self.assertEqual('count(/data/a)', XPath('/data/a').count())

    def test_eq_neq(self):
        self.assertEqual('a = b', XPath('a').eq('b'))
        self.assertEqual('a != b', XPath('a').neq('b'))

    def test_if(self):
        self.assertEqual('if(a, b, c)', XPath.if_('a', 'b', 'c'))

    def test_and_or(self):
        self.assertEqual('a and b and c', XPath.and_('a', 'b', 'c'))
        self.assertEqual('a and (b and c)', XPath.and_('a', XPath.and_('b', 'c')))

        self.assertEqual('a or b or c', XPath.or_('a', 'b', 'c'))
        self.assertEqual('(a or b) or c', XPath.or_(XPath.or_('a', 'b'), XPath('c')))

    def test_not(self):
        self.assertEqual('not a', XPath.not_('a'))
        self.assertEqual('not (a or b)', XPath.not_(XPath.or_('a', 'b')))

    def test_date(self):
        self.assertEqual('date(a)', XPath.date('a'))

    def test_int(self):
        self.assertEqual('int(a)', XPath.int('a'))

    def test_complex(self):
        xp = XPath.and_(
            XPath('a').eq('1'),
            XPath('b').neq(XPath.string('')),
            XPath.or_(
                XPath('c').eq(XPath.string('')),
                XPath.date('d').neq('today()')
            ))
        self.assertEqual("a = 1 and b != '' and (c = '' or date(d) != today())", xp)
