from xml.etree import ElementTree

class FormattedDetailColumn(object):

    hide_header = False

    def __init__(self, module, detail, column, forloop_counter):
        self.module = module
        self.detail = detail
        self.column = column
        self.forloop_counter = forloop_counter


    @property
    def locale_id(self):
        return u"m{module.id}.{detail.type}.{d.model}_{d.field}_{forloop_counter}.header".format(
            detail=self.detail,
            module=self.module,
            d=self.column,
            forloop_counter=self.forloop_counter,
        )

    def header(self):
        x_header = ElementTree.Element('header')
        if self.hide_header:
            x_header.attrib['width'] = "0"
        x_text = ElementTree.SubElement(x_header, 'text')
        x_locale = ElementTree.SubElement(x_text, 'locale', {'id': self.locale_id})
        return x_header

class PlainColumn(FormattedDetailColumn):
    pass

class HideHeaderColumn(FormattedDetailColumn):

    @property
    def hide_header(self):
        return self.detail.display == 'short'

class LateFlagColumn(HideHeaderColumn):
    pass

class InvisibleColumn(HideHeaderColumn):
    pass

class AddressColumn(HideHeaderColumn):
    pass
