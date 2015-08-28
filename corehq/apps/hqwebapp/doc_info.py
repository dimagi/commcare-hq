from couchdbkit import ResourceNotFound
from dimagi.utils.couch.undo import DELETED_SUFFIX
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from dimagi.ext.jsonobject import *
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import raw_username
from couchforms import models as couchforms_models


class DocInfo(JsonObject):
    id = StringProperty()
    domain = StringProperty()
    type = StringProperty()

    display = StringProperty()
    link = StringProperty()
    type_display = StringProperty()
    is_deleted = BooleanProperty()


def get_doc_info_by_id(domain, id):
    not_found_value = DocInfo(display=id, link=None, owner_type=None)
    if not id:
        return not_found_value
    try:
        doc = CouchUser.get_db().get(id)
    except ResourceNotFound:
        return not_found_value

    if doc.get('domain') != domain and domain not in doc.get('domains', ()):
        return not_found_value

    return get_doc_info(doc, domain_hint=domain)


def get_doc_info(doc, domain_hint=None, cache=None):
    """
    cache is just a dictionary that you can keep passing in to speed up info
    retrieval.
    """
    domain = doc.get('domain') or domain_hint
    doc_type = doc.get('doc_type')
    doc_id = doc.get('_id')
    generic_delete = doc_type.endswith(DELETED_SUFFIX)

    def has_doc_type(doc_type, expected_doc_type):
        return (doc_type == expected_doc_type or
            doc_type == ('%s%s' % (expected_doc_type, DELETED_SUFFIX)))

    assert doc.get('domain') == domain or domain in doc.get('domains', ())

    if cache and doc_id in cache:
        return cache[doc_id]

    if has_doc_type(doc_type, 'Application') or has_doc_type(doc_type, 'RemoteApp'):
        if doc.get('copy_of'):
            doc_info = DocInfo(
                display=u'%s (#%s)' % (doc['name'], doc['version']),
                type_display=_('Application Build'),
                link=reverse(
                    'corehq.apps.app_manager.views.download_index',
                    args=[domain, doc_id],
                ),
                is_deleted=generic_delete,
            )
        else:
            doc_info = DocInfo(
                display=doc['name'],
                type_display=_('Application'),
                link=reverse(
                    'corehq.apps.app_manager.views.view_app',
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
        doc_info = DocInfo(
            display=doc['name'],
            type_display=_('Case'),
            link=reverse(
                'case_details',
                args=[domain, doc_id],
            ),
            is_deleted=generic_delete,
        )
    elif any([has_doc_type(doc_type, d) for d in couchforms_models.doc_types().keys()]):
        doc_info = DocInfo(
            type_display=_('Form'),
            link=reverse(
                'render_form_data',
                args=[domain, doc_id],
            ),
            is_deleted=generic_delete,
        )
    elif doc_type in ('CommCareUser',):
        doc_info = DocInfo(
            display=raw_username(doc['username']),
            type_display=_('Mobile Worker'),
            link=reverse(
                'edit_commcare_user',
                args=[domain, doc_id],
            ),
            is_deleted=doc.get('base_doc', '').endswith(DELETED_SUFFIX),
        )
    elif doc_type in ('WebUser',):
        doc_info = DocInfo(
            type_display=_('Web User'),
            display=doc['username'],
            link=reverse(
                'user_account',
                args=[domain, doc_id],
            ),
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
                kwargs={'domain' : doc['name']}
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


def get_object_info(obj, cache=None):
    """
    This function is intended to behave just like get_doc_info, only
    you call it with objects other than Couch docs (such as objects
    that use the Django ORM).
    """
    class_name = obj.__class__.__name__
    cache_key = '%s-%s' % (class_name, obj.pk)
    if cache and cache_key in cache:
        return cache[cache_key]

    from corehq.apps.locations.models import SQLLocation
    if isinstance(obj, SQLLocation):
        from corehq.apps.locations.views import EditLocationView
        doc_info = DocInfo(
            type_display=_('Location'),
            display=obj.name,
            link=reverse(
                EditLocationView.urlname,
                args=[obj.domain, obj.location_id],
            ),
            is_deleted=False,
        )
    else:
        doc_info = DocInfo(
            is_deleted=False,
        )

    doc_info.id = str(obj.pk)
    doc_info.domain = obj.domain if hasattr(obj, 'domain') else None
    doc_info.type = class_name

    if cache:
        cache[cache_key] = doc_info

    return doc_info
