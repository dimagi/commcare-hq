from __future__ import absolute_import
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import ResourceNotFound
from tastypie.bundle import Bundle


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
        doc_json = cls.get_db().get(doc_id)
        if doc_json['doc_type'] not in additional_doc_types:
            raise ResourceNotFound
        doc = cls.wrap(doc_json)
        if doc and doc.domain == domain:
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


def get_obj(bundle_or_obj):
    if isinstance(bundle_or_obj, Bundle):
        return bundle_or_obj.obj
    else:
        return bundle_or_obj


def form_to_es_form(xform_instance, include_attachments=False):
    # include_attachments is only relevant for SQL domains; they're always
    # included for Couch domains
    from corehq.pillows.xform import transform_xform_for_elasticsearch, xform_pillow_filter
    from corehq.apps.api.models import ESXFormInstance
    from corehq.form_processor.models import XFormInstanceSQL

    if include_attachments and isinstance(xform_instance, XFormInstanceSQL):
        json_form = xform_instance.to_json(include_attachments=True)
    else:
        json_form = xform_instance.to_json()
    if not xform_pillow_filter(json_form):
        es_form = transform_xform_for_elasticsearch(json_form)
        return ESXFormInstance(es_form)


def case_to_es_case(case):
    from corehq.pillows.case import transform_case_for_elasticsearch
    from corehq.apps.api.models import ESCase
    return ESCase(transform_case_for_elasticsearch(case.to_json()))
