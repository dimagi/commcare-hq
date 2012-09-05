from couchdbkit.ext.django.schema import Document, StringProperty, ListProperty, \
    DocumentSchema, BooleanProperty, DictProperty, IntegerProperty
from dimagi.utils.couch.database import get_db

FORM_KEY_TYPES = (('user', 'form.meta.user_id'))
CASE_KEY_TYPES = (('case_type', 'type'), ('project', 'domain'), ('user', 'user_id'))
KEY_TYPES = ('user', 'case_type')


class ADMColumn(Document):
    name = StringProperty()
    description = StringProperty()

    def value(self, domain, key_id,
              startdate=None, enddate=None):
        return ""

    def format_display(self, key_id):
        return ""

    _couch_view = "adm/foo"
    def _results(self, startdate, enddate):
        return get_db().view(self._couch_view,

        )

class ADMCompareColumn(ADMColumn):
    """
        This is a shell of a proposal when we decide to allow more generic, customizable ADM columns.
    """
    numerator_id = StringProperty() # takes the id of an ADMColumn
    denominator_id = StringProperty() # takes the id of an ADMVolumn


#class ADMValueColumn(ADMColumn):
#    """
#        This is a shell of a proposal when we decide to allow more generic, customizable ADM columns.
#    """
#    forms = ListProperty() # list of xmlns
#    cases = ListProperty() # list of case_type names
#    form_maps = DictProperty() # ex: { "xmlns_id": "map fn specific to property and return value" }
#    case_maps = StringProperty()
#




class ADMReport(Document):
    columns = ListProperty() # list of column ids
    key_type = StringProperty()
    domain = StringProperty()