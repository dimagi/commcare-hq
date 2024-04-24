from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.hqwebapp.doc_lookup import lookup_doc_id
from corehq.apps.locations.permissions import can_edit_form_location, user_can_access_case
from corehq.apps.users.models import HqPermissions
from corehq.apps.users.util import raw_username
from corehq.form_processor.models import XFormInstance
from dimagi.ext.jsonobject import BooleanProperty, JsonObject, StringProperty
from dimagi.utils.couch.undo import DELETED_SUFFIX


class DomainMismatchException(Exception):
    pass


class DocInfo(JsonObject):
    id = StringProperty()
    domain = StringProperty()
    type = StringProperty()

    display = StringProperty()
    link = StringProperty()
    type_display = StringProperty()
    is_deleted = BooleanProperty()

    def user_has_permissions(self, domain, user, doc):
        if self.type == "XFormInstance":
            return _check_form_permissions(domain, user, doc)
        elif self.type == "CommCareCase":
            return _check_case_permissions(domain, user, doc)
        else:
            return False


def get_doc_info_by_id(domain, id):
    not_found_value = DocInfo(display=id, link=None, owner_type=None)
    if not id:
        return not_found_value

    result = lookup_doc_id(id)
    if not result:
        return not_found_value

    doc = result.doc
    try:
        return get_doc_info(doc, domain_hint=domain)
    except DomainMismatchException:
        return not_found_value


def get_doc_info(doc, domain_hint=None, cache=None):
    """
    cache is just a dictionary that you can keep passing in to speed up info
    retrieval.
    """
    domains = ()
    if isinstance(doc, dict):
        domains = doc.get('domains', ())
        domain_hint = domain_hint or (domains[0] if domains else None)
        doc_info = get_doc_info_couch(doc, domain_hint, cache=cache)
    else:
        doc_info = get_doc_info_sql(doc, cache=cache)

    if domain_hint and not (
        doc_info.domain == domain_hint or domain_hint in domains
    ):
        raise DomainMismatchException("Doc '%s' does not match the domain_hint '%s'" % (doc_info.id, domain_hint))

    return doc_info


def get_doc_info_couch(doc, domain_hint=None, cache=None):
    """Return DocInfo objects for Couch doc dicts"""
    domain = doc.get('domain') or domain_hint
    doc_type = doc.get('doc_type')
    doc_id = doc.get('_id')
    generic_delete = doc_type.endswith(DELETED_SUFFIX)

    def has_doc_type(doc_type, expected_doc_type):
        return (doc_type == expected_doc_type
            or doc_type == ('%s%s' % (expected_doc_type, DELETED_SUFFIX)))

    if cache and doc_id in cache:
        return cache[doc_id]

    if (
        has_doc_type(doc_type, 'Application')
        or has_doc_type(doc_type, 'LinkedApplication')
        or has_doc_type(doc_type, 'RemoteApp')
    ):
        if doc.get('copy_of'):
            doc_info = DocInfo(
                display='%s (#%s)' % (doc['name'], doc['version']),
                type_display=_('Application Build'),
                link=reverse(
                    'download_index',
                    args=[domain, doc_id],
                ),
                is_deleted=generic_delete,
            )
        else:
            doc_info = DocInfo(
                display=doc['name'],
                type_display=_('Application'),
                link=reverse(
                    'view_app',
                    args=[domain, doc_id],
                ),
                is_deleted=generic_delete,
            )
    elif has_doc_type(doc_type, 'CommCareCaseGroup'):
        from corehq.apps.data_interfaces.views import CaseGroupCaseManagementView
        doc_info = DocInfo(
            type_display=_('Case Group'),
            display=doc['name'],
            link=reverse(
                CaseGroupCaseManagementView.urlname,
                args=[domain, doc_id],
            ),
            is_deleted=generic_delete,
        )
    elif has_doc_type(doc_type, 'CommCareCase'):
        doc_info = case_docinfo(domain, doc_id, doc['name'], generic_delete)
    elif any([has_doc_type(doc_type, d) for d in XFormInstance.DOC_TYPE_TO_STATE]):
        doc_info = form_docinfo(domain, doc_id, generic_delete)
    elif doc_type in ('CommCareUser',):
        doc_info = DocInfo(
            display=raw_username(doc['username']),
            type_display=_('Mobile Worker'),
            link=get_commcareuser_url(domain, doc_id),
            is_deleted=doc.get('base_doc', '').endswith(DELETED_SUFFIX),
        )
    elif doc_type in ('WebUser',):
        doc_info = DocInfo(
            type_display=_('Web User'),
            display=doc['username'],
            link=get_webuser_url(domain, doc_id),
            is_deleted=doc.get('base_doc', '').endswith(DELETED_SUFFIX),
        )
    elif has_doc_type(doc_type, 'Group'):
        from corehq.apps.users.views.mobile import EditGroupMembersView
        doc_info = DocInfo(
            type_display=_('Group'),
            display=doc['name'],
            link=reverse(
                EditGroupMembersView.urlname,
                args=[domain, doc_id],
            ),
            is_deleted=generic_delete,
        )
    elif has_doc_type(doc_type, 'Domain'):
        if doc['is_snapshot'] and doc['published']:
            urlname = 'project_info'
        else:
            urlname = 'domain_basic_info'
        doc_info = DocInfo(
            type_display=_('Domain'),
            display=doc['name'],
            link=reverse(
                urlname,
                kwargs={'domain': doc['name']}
            ),
            is_deleted=generic_delete,
        )
    elif has_doc_type(doc_type, 'Location'):
        from corehq.apps.locations.views import EditLocationView
        doc_info = DocInfo(
            type_display=_('Location'),
            display=doc['name'],
            link=reverse(
                EditLocationView.urlname,
                args=[domain, doc_id],
            ),
            is_deleted=generic_delete,
        )
    else:
        doc_info = DocInfo(
            is_deleted=generic_delete,
        )

    doc_info.id = doc_id
    doc_info.domain = domain
    doc_info.type = doc_type

    if cache:
        cache[doc_id] = doc_info

    return doc_info


def form_docinfo(domain, doc_id, is_deleted):
    doc_info = DocInfo(
        id=doc_id,
        type="XFormInstance",
        type_display=_('Form'),
        link=get_form_url(domain, doc_id),
        is_deleted=is_deleted,
    )
    return doc_info


def case_docinfo(domain, doc_id, name, is_deleted):
    return DocInfo(
        id=doc_id,
        type="CommCareCase",
        display=name,
        type_display=_('Case'),
        link=get_case_url(domain, doc_id),
        is_deleted=is_deleted,
    )


def get_case_url(domain, case_id):
    return reverse(
        'case_data',
        args=[domain, case_id],
    )


def get_form_url(domain, form_id):
    return reverse(
        'render_form_data',
        args=[domain, form_id],
    )


def get_commcareuser_url(domain, user_id):
    return reverse(
        'edit_commcare_user',
        args=[domain, user_id],
    )


def get_webuser_url(domain, user_id):
    return reverse(
        'user_account',
        args=[domain, user_id],
    )


def get_doc_info_sql(obj, cache=None):
    """
    Return DocInfo objects for SQL models
    """
    class_name = obj.__class__.__name__
    cache_key = '%s-%s' % (class_name, obj.pk)
    if cache and cache_key in cache:
        return cache[cache_key]

    from corehq.apps.locations.models import SQLLocation
    from corehq.form_processor.models import CommCareCase
    if isinstance(obj, SQLLocation):
        from corehq.apps.locations.views import EditLocationView
        doc_info = DocInfo(
            id=obj.location_id,
            type="Location",
            type_display=_('Location'),
            display=obj.name,
            link=reverse(
                EditLocationView.urlname,
                args=[obj.domain, obj.location_id],
            ),
            is_deleted=False,
        )
    elif isinstance(obj, CommCareCase):
        doc_info = case_docinfo(obj.domain, obj.case_id, obj.name, obj.is_deleted)
    elif isinstance(obj, XFormInstance):
        doc_info = form_docinfo(obj.domain, obj.form_id, obj.is_deleted)
    else:
        doc_info = DocInfo(
            is_deleted=False,
        )

    doc_info.id = doc_info.id or str(obj.pk)
    doc_info.domain = obj.domain if hasattr(obj, 'domain') else None
    doc_info.type = doc_info.type or class_name

    if cache:
        cache[cache_key] = doc_info

    return doc_info


def get_object_url(domain, doc_type, doc_id):
    if doc_type == 'CommCareCase':
        return get_case_url(domain, doc_id)
    elif doc_type == 'CommCareUser':
        return get_commcareuser_url(domain, doc_id)
    elif doc_type == 'WebUser':
        return get_webuser_url(domain, doc_id)

    return None


def _check_form_permissions(domain, user, form):
    return (
        user.has_permission(
            domain, HqPermissions.view_report, "corehq.apps.reports.standard.inspect.SubmitHistory"
        )
        and can_edit_form_location(domain, user, form)
    )


def _check_case_permissions(domain, user, case):
    return (
        user.has_permission(
            domain, HqPermissions.view_report, "corehq.apps.reports.standard.cases.basic.CaseListReport"
        )
        and user_can_access_case(domain, user, case)
    )
