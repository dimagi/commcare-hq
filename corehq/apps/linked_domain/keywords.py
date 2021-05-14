import uuid

from django.utils.translation import ugettext as _

from corehq.apps.linked_domain.applications import get_downstream_app_id
from corehq.apps.linked_domain.exceptions import DomainLinkError, MultipleDownstreamAppsError
from corehq.apps.sms.models import Keyword


def create_linked_keyword(domain_link, keyword_id):
    if domain_link.is_remote:
        raise DomainLinkError(_("Linking keywords to a remote link is not currently supported"))

    try:
        keyword = Keyword.objects.get(id=keyword_id, domain=domain_link.master_domain)
    except Keyword.DoesNotExist:
        raise DomainLinkError(
            _("Keyword does not exist in the upstream domain")
        )

    if Keyword.objects.filter(keyword=keyword.keyword, domain=domain_link.linked_domain).exists():
        raise DomainLinkError(
            _("Keyword {keyword} already exists in downstream domain {domain}").format(
                keyword=keyword.keyword, domain=domain_link.linked_domain)
        )

    keyword_actions = keyword.keywordaction_set.all()

    keyword.upstream_id = keyword.id
    keyword.id = None
    keyword.domain = domain_link.linked_domain
    keyword.couch_id = uuid.uuid4().hex
    keyword.save()

    try:
        _update_actions(domain_link, keyword, keyword_actions)
    except DomainLinkError as e:
        keyword.delete()
        raise e

    return keyword.id


def update_keyword(domain_link, keyword_id):
    try:
        linked_keyword = Keyword.objects.get(id=keyword_id)
    except Keyword.DoesNotExist:
        raise DomainLinkError(
            _("Linked keyword could not be found")
        )
    try:
        master_keyword = Keyword.objects.get(id=linked_keyword.upstream_id)
    except Keyword.DoesNotExist:
        raise DomainLinkError(
            _("Upstream keyword could not be found. Maybe it has been deleted?")
        )

    for prop in ['keyword', 'description', 'delimiter', 'override_open_sessions', 'initiator_doc_type_filter']:
        setattr(linked_keyword, prop, getattr(master_keyword, prop))

    linked_keyword.save()

    _update_actions(domain_link, linked_keyword, master_keyword.keywordaction_set.all())


def _update_actions(domain_link, linked_keyword, keyword_actions):
    linked_keyword.keywordaction_set.all().delete()
    for keyword_action in keyword_actions:
        keyword_action.id = None
        keyword_action.keyword = linked_keyword
        if keyword_action.app_id is not None:
            try:
                app_id = get_downstream_app_id(domain_link.linked_domain, keyword_action.app_id)
            except MultipleDownstreamAppsError:
                raise DomainLinkError(_("Keyword {keyword} references an application that has multiple linked "
                                        "applications. It cannot be updated.").format(
                                            keyword=linked_keyword.keyword))
            if not app_id:
                raise DomainLinkError(_("Keyword {keyword} references an application "
                                        "that has not been linked to {linked_domain}").format(
                                            keyword=linked_keyword.keyword,
                                            linked_domain=domain_link.linked_domain))
            keyword_action.app_id = app_id
        keyword_action.save()


def unlink_keywords_in_domain(domain):
    unlinked_keywords = []
    keywords = Keyword.objects.filter(domain=domain, upstream_id__isnull=False)
    for keyword in keywords:
        unlinked_keyword = unlink_keyword(keyword)
        unlinked_keywords.append(unlinked_keyword)

    return unlinked_keywords


def unlink_keyword(keyword):
    if not keyword.upstream_id:
        return None

    keyword.upstream_id = None
    keyword.save()

    return keyword
