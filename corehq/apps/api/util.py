from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound

def get_object_or_not_exist(cls, doc_id, domain):
    """
    Given a Document class, id, and domain, get that object or raise
    an ObjectDoesNotExist exception if it's not found, not the right
    type, or doesn't belong to the domain.
    """
    doc_type = getattr(cls, '_doc_type', cls.__name__)
    try:
        doc = cls.get(doc_id)
        if doc and doc.domain == domain and doc.doc_type == doc_type:
            return doc
    except ResourceNotFound:
        pass # covered by the below
    except AttributeError:
        # there's a weird edge case if you reference a form with a case id
        # that explodes on the "version" property. might as well swallow that
        # too.
        pass
    raise ObjectDoesNotExist(_("Could not find %(doc_type)s with id %(id)s") % \
                                {"doc_type": doc_type, "id": doc_id})
