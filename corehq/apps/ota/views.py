from corehq.apps.domain.decorators import login_or_digest_ex
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from corehq.util.view_utils import json_error
from couchforms.models import XFormInstance
from django_digest.decorators import *
from casexml.apps.phone.restore import RestoreConfig
from django.http import HttpResponse
from lxml import etree


@json_error
@httpdigest
def restore(request, domain):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    user = request.user
    couch_user = CouchUser.from_django_user(user)
    return get_restore_response(domain, couch_user, **get_restore_params(request))


def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "1.0"),
        'state': request.GET.get('state'),
        'items': request.GET.get('items') == 'true'
    }


def get_restore_response(domain, couch_user, since=None, version='1.0',
                         state=None, items=False, force_cache=False,
                         cache_timeout=None, overwrite_cache=False):
    # not a view just a view util
    if not couch_user.is_commcare_user():
        return HttpResponse("No linked chw found for %s" % couch_user.username,
                            status=401)  # Authentication Failure
    elif domain != couch_user.domain:
        return HttpResponse("%s was not in the domain %s" % (couch_user.username, domain),
                            status=401)

    project = Domain.get_by_name(domain)
    commtrack_settings = project.commtrack_settings
    stock_settings = commtrack_settings.get_ota_restore_settings() if commtrack_settings else None
    restore_config = RestoreConfig(
        couch_user.to_casexml_user(), since, version, state,
        items=items,
        stock_settings=stock_settings,
        domain=project,
        force_cache=force_cache,
        cache_timeout=cache_timeout,
        overwrite_cache=overwrite_cache
    )
    return restore_config.get_response()


@login_or_digest_ex(allow_cc_users=True)
def historical_forms(request, domain):
    assert request.couch_user.is_member_of(domain)
    user_id = request.couch_user.get_id
    db = XFormInstance.get_db()
    form_ids = {
        f['id'] for f in db.view(
            'reports_forms/all_forms',
            startkey=["submission user", domain, user_id],
            endkey=["submission user", domain, user_id, {}],
            reduce=False,
        )
    }

    def data():
        yield (
            '<OpenRosaResponse xmlns="http://openrosa.org/http/response" '
            'items="{}">\n    <message nature="success"/>\n'
            .format(len(form_ids))
        )

        for form_id in form_ids:
            # this is a hack to call this method
            # Should only hit couch once per form, to get the attachment
            xml = XFormInstance(_id=form_id).get_xml_element()
            if xml:
                yield '    {}'.format(etree.tostring(xml))
            else:
                yield '    <XFormNotFound/>'
            yield '\n'
        yield '</OpenRosaResponse>\n'

    # to make this not stream, just call list on data()
    return HttpResponse(data(), content_type='application/xml')
