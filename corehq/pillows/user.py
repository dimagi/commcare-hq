from casexml.apps.case.xform import is_device_report
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.elastic import ES_URLS, stream_es_query, get_es, doc_exists_in_es
from corehq.pillows.mappings.user_mapping import USER_MAPPING, USER_INDEX
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import get_default_django_checkpoint_for_legacy_pillow_class
from pillowtop.listener import AliasedElasticPillow, PythonPillow
from django.conf import settings


class UserPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = CommCareUser   # while this index includes all users,
                                    # I assume we don't care about querying on properties specific to WebUsers
    couch_filter = "users/all_users"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 60
    es_alias = "hqusers"
    es_type = "user"
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }
    es_index = USER_INDEX
    default_mapping = USER_MAPPING

    @classmethod
    def get_unique_id(self):
        return USER_INDEX

    def change_transform(self, doc_dict):
        super(UserPillow, self).change_transform(doc_dict)
        doc_dict = self._cast_user_data_to_string(doc_dict)
        return doc_dict

    def _cast_user_data_to_string(self, doc_dict):
        """
        Make all user_data strings
        ES doesn't allow dynamic dicts with the same key name to have different types, so coerce everything
        """
        user_data = doc_dict.get('user_data', {})
        if user_data and type(user_data) is dict:
            for k, v in user_data.iteritems():
                try:
                    doc_dict['user_data'][k] = unicode(v)
                except UnicodeDecodeError:
                    doc_dict['user_data'][k] = v  # If we can't decode it, let elastic deal with it
        return doc_dict


class GroupToUserPillow(PythonPillow):
    document_class = CommCareUser

    def __init__(self):
        checkpoint = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(GroupToUserPillow, self).__init__(checkpoint=checkpoint)

    def python_filter(self, change):
        return change.document.get('doc_type', None) in ('Group', 'Group-Deleted')

    def change_transport(self, doc_dict):
        es = get_es()
        user_ids = doc_dict.get("users", [])
        q = {"filter": {"and": [{"terms": {"_id": user_ids}}]}}
        for user_source in stream_es_query(es_url=ES_URLS["users"], q=q, fields=["__group_ids", "__group_names"]):
            group_ids = set(user_source.get('fields', {}).get("__group_ids", []))
            group_names = set(user_source.get('fields', {}).get("__group_names", []))
            if doc_dict["name"] not in group_names or doc_dict["_id"] not in group_ids:
                group_ids.add(doc_dict["_id"])
                group_names.add(doc_dict["name"])
                doc = {"__group_ids": list(group_ids), "__group_names": list(group_names)}
                es.post("%s/user/%s/_update" % (USER_INDEX, user_source["_id"]), data={"doc": doc})


class UnknownUsersPillow(PythonPillow):
    """
    This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    document_class = XFormInstance
    include_docs_when_preindexing = False
    es_path = USER_INDEX + "/user/"

    def __init__(self):
        checkpoint = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(UnknownUsersPillow, self).__init__(checkpoint=checkpoint)
        self.user_db = CouchUser.get_db()
        self.es = get_es()

    def python_filter(self, change):
        # designed to exactly mimic the behavior of couchforms/filters/xforms.js
        doc = change.document
        return doc.get('doc_type', None) in all_known_formlike_doc_types() and not is_device_report(doc)

    def get_fields_from_doc(self, doc):
        form_meta = doc.get('form', {}).get('meta', {})
        domain = doc.get('domain')
        user_id = form_meta.get('userID')
        username = form_meta.get('username')
        xform_id = doc.get('_id')
        return user_id, username, domain, xform_id

    @memoized
    def _user_exists(self, user_id):
        return self.user_db.doc_exist(user_id)

    def _user_indexed(self, user_id):
        return doc_exists_in_es('users', user_id)

    def change_transport(self, doc_dict):
        doc = doc_dict
        user_id, username, domain, xform_id = self.get_fields_from_doc(doc)

        if user_id in WEIRD_USER_IDS:
            user_id = None

        if (user_id and not self._user_exists(user_id)
                and not self._user_indexed(user_id)):
            doc_type = "AdminUser" if username == "admin" else "UnknownUser"
            doc = {
                "_id": user_id,
                "domain": domain,
                "username": username,
                "first_form_found_in": xform_id,
                "doc_type": doc_type,
            }
            if domain:
                doc["domain_membership"] = {"domain": domain}
            self.es.put(self.es_path + user_id, data=doc)


def add_demo_user_to_user_index():
    es = get_es()
    es_path = USER_INDEX + "/user/demo_user"
    es.put(es_path, data={"_id": "demo_user", "username": "demo_user", "doc_type": "DemoUser"})
