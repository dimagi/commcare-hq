import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from couchdbkit.exceptions import ResourceNotFound
from dateutil.parser import parse
from tastypie.bundle import Bundle

from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter


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
    from corehq.apps.api.models import ESXFormInstance
    from corehq.form_processor.models import XFormInstance
    from corehq.pillows.xform import xform_pillow_filter

    if include_attachments and isinstance(xform_instance, XFormInstance):
        json_form = xform_instance.to_json(include_attachments=True)
    else:
        json_form = xform_instance.to_json()
    if not xform_pillow_filter(json_form):
        es_form = form_adapter.to_json(json_form)
        return ESXFormInstance(es_form)


def case_to_es_case(case):
    from corehq.apps.api.models import ESCase
    return ESCase(case_adapter.to_json(case))


def make_date_filter(date_filter):
    """Function builder that returns a function for processing API date
    parameters.

    :param date_filter: a function which is called with the final value
        of the filter parameters.
    """

    def filter_fn(param, val):
        if param not in ['gt', 'gte', 'lt', 'lte']:
            raise ValueError(_("'{param}' is not a valid type of date range.").format(param=param))
        val = parse_str_to_date(val)
        return date_filter(**{param: val})

    return filter_fn


def parse_str_to_date(val):
    try:
        # If it's only a date, don't turn it into a datetime
        val = datetime.datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        try:
            val = parse(val)
        except ValueError:
            raise ValueError(_("Cannot parse datetime '{val}'").format(val=val))
    return val


def django_date_filter(field_name, gt=None, gte=None, lt=None, lte=None):
    """Return a dictionary mapping Django field filter names to filter values.

    filters = django_date_filter("created_on", gt=d1, lte=d2)
    Model.objects.filter(**filters)
    """
    params = dict(zip(['gt', 'gte', 'lt', 'lte'], [gt, gte, lt, lte]))

    def _adjust_lte_date(param, value):
        """Adjust `lte` when value is date (not datetime) so that it is inclusive of all data
        in the day.
        """
        if param != 'lte' or isinstance(value, datetime.datetime):
            return value

        return datetime.datetime.combine(value, datetime.datetime.max.time())

    return {
        f"{field_name}__{param}": _adjust_lte_date(param, value)
        for param, value in params.items()
        if value is not None
    }
