from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.elastic import es_query, ES_URLS, stream_es_query, get_es
from corehq.pillows.mappings.user_mapping import USER_MAPPING, USER_INDEX
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow, BasicPillow
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

class GroupToUserPillow(BasicPillow):
    couch_filter = "groups/all_groups"

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
