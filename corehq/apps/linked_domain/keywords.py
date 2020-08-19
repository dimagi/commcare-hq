import uuid

from corehq.apps.sms.models import Keyword
from corehq.apps.app_manager.dbaccessors import get_brief_app_docs_in_domain


def create_linked_keyword(domain_link, keyword_id):
    # if domain_link.is_remote...

    try:
        keyword = Keyword.objects.get(id=keyword_id, domain=domain_link.master_domain)
    except Keyword.DoesNotExist:
        return

    keyword_actions = keyword.keywordaction_set.all()

    keyword.id = None
    keyword.domain = domain_link.linked_domain
    keyword.couch_id = uuid.uuid4().hex
    keyword.save()

    master_app_to_linked_app = {
        doc["family_id"]: doc["_id"]
        for doc in get_brief_app_docs_in_domain(domain_link.linked_domain)
        if doc.get("family_id", None) is not None
    }

    for keyword_action in keyword_actions:
        keyword_action.pk = None
        keyword_action.keyword = keyword
        if keyword_action.app_id is not None:
            keyword_action.app_id = master_app_to_linked_app[keyword_action.app_id]
        keyword_action.save()
