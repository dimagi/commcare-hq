from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.elastic import es_query, ES_URLS, stream_es_query, get_es
from corehq.pillows.mappings.user_mapping import USER_MAPPING, USER_INDEX
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow, BulkPillow
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
    es_index_prefix = "hqusers"
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

    @memoized
    def calc_meta(self):
        #todo: actually do this correctly

        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return self.calc_mapping_hash({"es_meta": self.es_meta,
                                       "mapping": self.default_mapping})

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the user_type document.
        See below on why date_detection is False

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all are strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

    def get_type_string(self, doc_dict):
        return self.es_type

class GroupToUserPillow(BulkPillow):
    couch_filter = "groups/all_groups"
    document_class = CommCareUser

    def __init__(self, **kwargs):
        super(GroupToUserPillow, self).__init__(**kwargs)
        self.couch_db = Group.get_db()

    def change_trigger(self, changes_dict):
        es = get_es()
        user_ids = changes_dict["doc"].get("users", [])
        q = {"filter": {"and": [{"terms": {"_id": user_ids}}]}}
        for user_source in stream_es_query(es_url=ES_URLS["users"], q=q, fields=["__group_ids", "__group_names"]):
            group_ids = set(user_source.get('fields', {}).get("__group_ids", []))
            group_names = set(user_source.get('fields', {}).get("__group_names", []))
            if changes_dict["doc"]["name"] not in group_names or changes_dict["doc"]["_id"] not in group_ids:
                group_ids.add(changes_dict["doc"]["_id"])
                group_names.add(changes_dict["doc"]["name"])
                doc = {"__group_ids": list(group_ids), "__group_names": list(group_names)}
                es.post("%s/user/%s/_update" % (USER_INDEX, user_source["_id"]), data={"doc": doc})

    def change_transport(self, doc_dict):
        pass

    def send_bulk(self, payload):
        pass


class UnknownUsersPillow(BulkPillow):
    """
        This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    document_class = XFormInstance
    couch_filter = "couchforms/xforms"
    include_docs_when_preindexing = False

    def __init__(self, **kwargs):
        super(UnknownUsersPillow, self).__init__(**kwargs)
        self.couch_db = XFormInstance.get_db()
        self.user_db = CouchUser.get_db()
        self.es = get_es()

    def get_fields_from_emitted_dict(self, emitted_dict):
        domain = emitted_dict['key'][1]
        user_id = emitted_dict['value']['user_id']
        username = emitted_dict['value']['username']
        xform_id = emitted_dict['id']
        return user_id, username, domain, xform_id

    def get_fields_from_doc(self, doc):
        form_meta = doc.get('form', {}).get('meta', {})
        domain = doc.get('domain')
        user_id = form_meta.get('userID')
        username = form_meta.get('username')
        xform_id = doc.get('_id')
        return user_id, username, domain, xform_id

    def change_trigger(self, changes_dict):
        if 'key' in changes_dict:
            user_id, username, domain, xform_id = self.get_fields_from_emitted_dict(changes_dict)
        else:
            doc = changes_dict['doc'] if 'doc' in changes_dict else self.couch_db.open_doc(changes_dict['id'])
            user_id, username, domain, xform_id = self.get_fields_from_doc(doc)

        if user_id in WEIRD_USER_IDS:
            user_id = None

        es_path = USER_INDEX + "/user/"
        if (user_id and not self.user_db.doc_exist(user_id)
                and not self.es.head(es_path + user_id)):
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
            self.es.put(es_path + user_id, data=doc)

    def change_transport(self, doc_dict):
        pass

    def send_bulk(self, payload):
        pass


def add_demo_user_to_user_index():
    es = get_es()
    es_path = USER_INDEX + "/user/demo_user"
    es.put(es_path, data={"_id": "demo_user", "username": "demo_user", "doc_type": "DemoUser"})
