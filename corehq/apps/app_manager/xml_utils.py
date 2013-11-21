# File adapted from
# http://crispy-ajax.svn.sourceforge.net/viewvc/crispy-ajax/crispy/baseclasses.py?revision=1&content-type=text/plain
# XMLObject and XMLObjectType implement some syntax abuse that
# allows html to be written nicely in python
# tag(opt=val)[sub1, sub2] stands for <tag opt="val">sub1 sub2</tag>

class XMLObjectType(type):
    def __getitem__(cls, item):
        return cls()[item]

class XMLObject(object):
    __metaclass__ = XMLObjectType
    collapsable = True
    name = u""
    def __init__(self, name, **options):
        self.options = options
        self.name = name
        self.children = []
    def __getitem__(self, items):
        if isinstance(items, basestring) or isinstance(items, XMLObject):
            items = (items,)
        for item in items:
            if isinstance(item, tuple) or isinstance(item, list):
                self.children.extend(item)
            else:
                self.children.append(item)
        return self
    def structure(self):
        return self
    def render(self, depth=0):
        struct = self.structure()
        return struct.render(depth)
    def __unicode__(self):
        return self.render(None)

class XMLTag(XMLObject):
    name = ""
    def render(self, depth=0):
        children = []
        next_depth = depth + 1 if self.name else depth
        for child in self.children:
            if isinstance(child, XMLObject):
                child = child.render(depth+1)
            else:
                #child = "  "*(depth+1) + unicode(child)
                child = unicode(child)
            children.append(child)
        #children = u"\n".join(children)
        children = u"".join(children)

        if self.name:
            options = u"".join([u' %s="%s"' % (opt, val) for (opt, val) in self.options.items()])
            if (not children) and self.collapsable:
                return u"<%s%s />" % (self.name, options)
            else:
                return u"<%(name)s%(options)s>%(children)s</%(name)s>" % {
                    'name':self.name, 'options':options, 'children':children}
        else:
            return children

def session_var(var):
    return u"instance('commcaresession')/session/data/%s" % var

class XPath(unicode):
    def slash(self, xpath):
        if self:
            return XPath(u'%s/%s' % (self, xpath))
        else:
            return XPath(xpath)

    def select(self, ref, value):
        return XPath('{self}[{ref} = {value}]'.format(self=self, ref=ref, value=value))

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


class CaseXPath(XPath):

    def index_id(self, name):
        return CaseIDXPath(self.slash(u'index').slash(name))

    def parent_id(self):
        return self.index_id('parent')

    def property(self, property):
        return self.slash(property)
