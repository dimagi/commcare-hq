import uuid

from django.conf import settings
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import get_brief_app_docs_in_domain
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.sms.models import Keyword, KeywordAction
from corehq.util.quickcache import quickcache


def create_linked_keyword(domain_link, keyword_id):
    # if domain_link.is_remote...

    try:
        keyword = Keyword.objects.get(id=keyword_id, domain=domain_link.master_domain)
    except Keyword.DoesNotExist:
        return None

    keyword_actions = keyword.keywordaction_set.all()

    keyword.master_id = keyword.id
    keyword.id = None
    keyword.domain = domain_link.linked_domain
    keyword.couch_id = uuid.uuid4().hex
    keyword.save()

    for keyword_action in keyword_actions:
        keyword_action.master_id = keyword_action.id
        keyword_action.id = None
        keyword_action.keyword = keyword
        if keyword_action.app_id is not None:
            try:
                keyword_action.app_id = get_master_app_to_linked_app(domain_link.linked_domain)[keyword_action.app_id]
            except KeyError:
                raise DomainLinkError(_("Keyword references application that has not been linked"))
        keyword_action.save()

    return keyword.id


def update_keyword(domain_link, linked_keyword_id):
    linked_keyword = Keyword.objects.get(id=linked_keyword_id)
    master_keyword = Keyword.objects.get(id=linked_keyword.master_id)

    for prop in ['keyword', 'description', 'delimiter', 'override_open_sessions']:
        setattr(linked_keyword, prop, getattr(master_keyword, prop))

    linked_keyword.save()

    for linked_keywordaction in linked_keyword.keywordaction_set.all():
        master_keywordaction = KeywordAction.objects.get(id=linked_keywordaction.master_id)
        for prop in ['action', 'recipient', 'message_content']:
            setattr(linked_keywordaction, prop, getattr(master_keywordaction, prop))

        if master_keywordaction.app_id:
            try:
                app_id = get_master_app_to_linked_app(domain_link.linked_domain)[master_keywordaction.app_id]
            except KeyError:
                raise DomainLinkError(_("Keyword references application that has not been linked"))
            if linked_keywordaction.app_id != app_id:
                    linked_keywordaction.app_id = app_id

        linked_keywordaction.save()


@quickcache(vary_on=['domain'], skip_arg=lambda _: settings.UNIT_TESTING, timeout=5 * 60)
def get_master_app_to_linked_app(domain):
    return {
        doc["family_id"]: doc["_id"]
        for doc in get_brief_app_docs_in_domain(domain)
        if doc.get("family_id", None) is not None
    }
