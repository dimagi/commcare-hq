from lxml.builder import ElementMaker
from casexml.apps.stock import const

def _(tag, ns=const.COMMTRACK_REPORT_XMLNS):
    return '{%s}%s' % (ns, tag)
def XML(ns=const.COMMTRACK_REPORT_XMLNS, prefix=None):
    prefix_map = None
    if prefix:
        prefix_map = {prefix: ns}
    return ElementMaker(namespace=ns, nsmap=prefix_map)

