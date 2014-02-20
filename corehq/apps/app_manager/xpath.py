import re


def dot_interpolate(string, replacement):
    """
    Replaces non-decimal dots in `string` with `replacement`
    """
    pattern = r'(\D|^)\.(\D|$)'
    repl = '\g<1>%s\g<2>' % replacement
    return re.sub(pattern, repl, string)


def session_var(var):
    return u"instance('commcaresession')/session/data/%s" % var


class XPath(unicode):
    def slash(self, xpath):
        if self:
            return XPath(u'%s/%s' % (self, xpath))
        else:
            return XPath(xpath)

    def select(self, ref, value, quote=True):
        if quote:
            value = "'{val}'".format(val=value)
        return XPath("{self}[{ref}={value}]".format(self=self, ref=ref, value=value))

    def count(self):
        return XPath('count({self})'.format(self=self))


class CaseSelectionXPath(XPath):
    selector = ''

    def case(self):
        return CaseXPath(u"instance('casedb')/casedb/case[%s=%s]" % (self.selector, self))


class CaseIDXPath(CaseSelectionXPath):
    selector = '@case_id'


class CaseTypeXpath(CaseSelectionXPath):
    selector = '@case_type'

    def case(self):
        return CaseXPath(u"instance('casedb')/casedb/case[%s='%s']" % (self.selector, self))


class CaseXPath(XPath):

    def index_id(self, name):
        return CaseIDXPath(self.slash(u'index').slash(name))

    def parent_id(self):
        return self.index_id('parent')

    def property(self, property):
        return self.slash(property)


class IndicatorXpath(XPath):

    def indicator(self, indicator_name):
        return XPath(u"instance('%s')/indicators/case[@id = current()/@case_id]" % self).slash(indicator_name)


class LedgerdbXpath(XPath):

    def ledger(self):
        return LedgerXpath(u"instance('ledgerdb')/ledgerdb/ledger[@entity-id=instance('commcaresession')/session/data/%s]" % self)


class LedgerXpath(XPath):

    def section(self, section):
        return LedgerSectionXpath(self.slash(u'section').select(u'@section-id', section))


class LedgerSectionXpath(XPath):

    def entry(self, id):
        return XPath(self.slash(u'entry').select(u'@id', id, quote=False))

