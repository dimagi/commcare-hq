from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound

def get_object_or_not_exist(cls, doc_id, domain, additional_doc_types=None):
    """
    Given a Document class, id, and domain, get that object or raise
    an ObjectDoesNotExist exception if it's not found, not the right
    type, or doesn't belong to the domain.
    """
    additional_doc_types = additional_doc_types or []
    doc_type = getattr(cls, '_doc_type', cls.__name__)
    additional_doc_types.append(doc_type)
    try:
        doc = cls.get(doc_id)
        if doc and doc.domain == domain and doc.doc_type in additional_doc_types:
            return doc
    except ResourceNotFound:
        pass # covered by the below
    except AttributeError:
        # there's a weird edge case if you reference a form with a case id
        # that explodes on the "version" property. might as well swallow that
        # too.
        pass

    raise object_does_not_exist(doc_type, doc_id)

def object_does_not_exist(doc_type, doc_id):
    """
    Builds a 404 error message with standard, translated, verbiage
    """
    return ObjectDoesNotExist(_("Could not find %(doc_type)s with id %(id)s") % \
                              {"doc_type": doc_type, "id": doc_id})

