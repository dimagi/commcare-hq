from couchdbkit import ResourceNotFound
from django.http import Http404
from jsonobject.exceptions import WrappingAttributeError


def get_document_or_404(cls, domain, doc_id, additional_doc_types=None):
    """
    Gets a document and enforces its domain and doc type.
    Raises Http404 if the doc isn't found or domain/doc_type don't match.
    """
    allowed_doc_types = (additional_doc_types or []) + [cls.__name__]
    try:
        wrapped = cls.get(doc_id)
    except (ResourceNotFound, WrappingAttributeError):
        raise Http404()

    if wrapped.domain != domain or wrapped.doc_type not in allowed_doc_types:
        raise Http404()

    return wrapped
