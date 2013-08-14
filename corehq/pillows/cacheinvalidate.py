import simplejson
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.cache import cache_core
from pillowtop.listener import BasicPillow


class CacheInvalidatePillow(BasicPillow):
    couch_filter = "hqadmin/not_case_form"  # string for filter if needed

    def __init__(self, *args, **kwargs):
        super(CacheInvalidatePillow, self).__init__(**kwargs)
        self.couch_db = Domain.get_db()

        #always set checkpoint to current when initializing
        current_db_seq = self.couch_db.info()['update_seq']
        self.set_checkpoint({'seq': current_db_seq})

    def change_trigger(self, changes_dict):
        """
        Step one of pillowtop process
        For a given _changes indicator, the changes dict (the id, _rev) is sent here.

        Note, a couch _changes line is: {'changes': [], 'id': 'guid',  'seq': <int>}
        a 'deleted': True might be there too

        whereas a doc_dict is _id
        Should return a doc_dict
        """

        doc_id = changes_dict['id']
        print "change_trigger: %s" % doc_id
        rcache = cache_core.rcache()

        #purge cache regardless
        cache_core.purge_by_doc_id(doc_id)

        if changes_dict.get('deleted', False):
            #we're done
            return None

        doc = self.couch_db.open_doc(changes_dict['id'])
        doc_type = doc.get('doc_type', None)
        print "got doc_type: %s" % doc_type
        if doc_type in ['Domain']:
            self.invalidate_domain_views()
        elif doc_type in ['CommCareUser', 'WebUser', 'CouchUser']:
            self.invalidate_users()
        elif doc_type in ['Group', 'UserRole']:
            #here is where the hacky magic happens
            self.invalidate_groups()
        else:
            print "not relevant!"
            return None


    def invalidate_views(self, views):
        rcache = cache_core.rcache()
        for view in views:
            print "invalidating view: %s" % view
            search = cache_core.key_view_partial("%s*" % view)
            live_keys = rcache.keys(search)
            for cache_view_key in live_keys:
                #open each view, purge all the reverse doc_ids
                cache_core.purge_view(cache_view_key)


    def invalidate_domain_views(self):
        """
        Overaggressive funcionality to blow away views and domains
        """
        domain_views = [
            "domain/not_snapshots",
            "domain/domains",
            "domain/counter",
            "domain/fields_by_prefix",
            "domain/by_status",
            "domain/by_organization",
        ]
        self.invalidate_views(domain_views)

    def invalidate_users(self):
        user_views = [
            "sms/phones_to_domains",
            "hqadmin/users_over_time",
            "users/by_domain",
            "users/phone_users_by_domain",
            "users/by_default_phone",
            "users/admins_by_domain",
            "users/by_org_and_team",
            "users/web_users_by_domain",
        ]
        self.invalidate_views(user_views)

    def invalidate_groups(self):
        group_views = [
            "groups/_design/views/by_user",
            "groups/_design/views/by_hierarchy_type",
            "groups/_design/views/by_user_type",
            "groups/_design/views/by_name",
            "groups/_design/views/all_groups",
            "groups/_design/views/by_domain",
            "users/by_group",
        ]

        self.invalidate_views(group_views)

    def change_transform(self, doc_dict):
        """
        Step two of the pillowtop processor:
        Process/transform doc_dict if needed - by default, return the doc_dict passed.
        """
        return None

    def change_transport(self, doc_dict):
        """
        Step three of the pillowtop processor:
        Finish transport of doc if needed. Your subclass should implement this
        """
        return None
