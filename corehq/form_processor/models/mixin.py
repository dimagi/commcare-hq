

class IsImageMixin:

    @property
    def is_image(self):
        if self.content_type is None:
            return None
        return True if self.content_type.startswith('image/') else False


class SaveStateMixin:

    def is_saved(self):
        return bool(self._get_pk_val())


class CaseToXMLMixin:
    def to_xml(self, version, include_case_on_closed=False):
        from lxml import etree as ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem, encoding='utf-8')
