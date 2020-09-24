import uuid

from django.conf import settings
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import get_brief_app_docs_in_domain
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.sms.models import Keyword, KeywordAction
from corehq.util.quickcache import quickcache


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

    keyword.master_id = keyword.id
    keyword.id = None
    keyword.domain = domain_link.linked_domain
    keyword.couch_id = uuid.uuid4().hex
    keyword.save()

    try:
        _update_actions(domain_link, keyword, keyword_actions)
    except DomainLinkError:
        keyword.delete()
        return None

    return keyword.id


def update_keyword(domain_link, linked_keyword_id):
    try:
        linked_keyword = Keyword.objects.get(id=linked_keyword_id)
    except Keyword.DoesNotExist:
        raise DomainLinkError(
            _("Linked keyword could not be found")
        )
    try:
        master_keyword = Keyword.objects.get(id=linked_keyword.master_id)
    except Keyword.DoesNotExist:
        raise DomainLinkError(
            _("Upstream keyword could not be found. Maybe it has been deleted?")
        )

    for prop in ['keyword', 'description', 'delimiter', 'override_open_sessions']:
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
                keyword_action.app_id = get_master_app_to_linked_app(domain_link.linked_domain)[
                    keyword_action.app_id
                ]
            except KeyError:
                raise DomainLinkError(_("Keyword {keyword} references an application "
                                        "that has not been linked to {linked_domain}").format(
                                            keyword=linked_keyword.keyword,
                                            linked_domain=domain_link.linked_domain))
        keyword_action.save()


@quickcache(vary_on=['domain'], skip_arg=lambda _: settings.UNIT_TESTING, timeout=5 * 60)
def get_master_app_to_linked_app(domain):
    return {
        doc["family_id"]: doc["_id"]
        for doc in get_brief_app_docs_in_domain(domain)
        if doc.get("family_id", None) is not None
    }
