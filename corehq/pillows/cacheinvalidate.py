import logging
from datetime import datetime

from corehq.apps.domain.models import Domain
from dimagi.utils.couch.cache import cache_core
from pillowtop.listener import BasicPillow, ms_from_timedelta


pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)

class CacheInvalidatePillow(BasicPillow):
    """
    Pillow that listens to non xform/case _changes and invalidates the cache whether it's a
    a single doc being cached, to a view.
    """
    couch_filter = "hqadmin/not_case_form"  # string for filter if needed

    def __init__(self, *args, **kwargs):
        super(CacheInvalidatePillow, self).__init__(**kwargs)
        self.couch_db = Domain.get_db()

        #always set checkpoint to current when initializing
        current_db_seq = self.couch_db.info()['update_seq']
        self.set_checkpoint({'seq': current_db_seq})

    def change_trigger(self, changes_dict):
        """
        Where all the magic happens.
        """

        doc_id = changes_dict['id']

        if doc_id.startswith('pillowtop_corehq.pillows'):
            return None

        #purge cache regardless
        existed, last_version = cache_core.purge_by_doc_id(doc_id)

        if changes_dict.get('deleted', False):
            #if deleted, see if we have the last doc
            doc = last_version if existed else {}
        else:
            doc = self.couch_db.open_doc(changes_dict['id'])

        doc_type = doc.get('doc_type', None)
        base_doc = doc.get('base_doc', None)
        pillow_logging.info("CacheInvalidate: received change event for doc_id: %s, doc_type: %s" % (doc_id, doc_type))

        if doc_type in ['Domain']:
            self.invalidate_domain_views()
        elif doc_type in ['CommCareUser', 'WebUser', 'CouchUser']:
            self.invalidate_users()
        elif doc_type in ['Group', 'UserRole']:
            self.invalidate_groups()
        elif doc_type in ['Organization', 'Team', 'OrgRequest', 'DeleteTeamRecord', 'OrgInvitation']:
            self.invalidate_orgs()
        elif base_doc in ['Notification', 'ReportAnnouncement', 'HQAnnouncement']:
            self.invalidate_announcements()
        else:
            return None


    def invalidate_views(self, views, name=None):
        """
        Nuclear option for cache invalidation
        Given a certain document class of highly interdependent views, just invalidate ALL views when
        that a doc_type is dependent on. This is because we cannot effectively handle the case where
        a NEW doc is added that would change a view.

        To update this list of views to update based upon doc_type, examine all view map functions
        that have a doc.doc_type to verify which doc_type it is beholden to.
        """
        rcache = cache_core.rcache()
        start = datetime.utcnow()

        total_keys = 0
        for view in views:
            search = cache_core.key_view_partial("%s*" % view)
            live_keys = rcache.keys(search)
            total_keys += len(live_keys)
            for cache_view_key in live_keys:
                #open each view, purge all the reverse doc_ids
                cache_core.purge_view(cache_view_key)

        stop = datetime.utcnow()
        duration = ms_from_timedelta(stop - start)
        pillow_logging.info("CacheInvalidate: invalidate_views(%s) completed %d keys in %s ms" % (name, total_keys, duration))

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
        self.invalidate_views(domain_views, name="domains")

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
        self.invalidate_views(user_views, name="users")

    def invalidate_groups(self):
        group_views = [
            "groups/by_user",
            "groups/by_hierarchy_type",
            "groups/by_user_type",
            "groups/by_name",
            "groups/all_groups",
            "groups/by_domain",
            "users/by_group",
        ]

        self.invalidate_views(group_views, name="groups")

    def invalidate_announcements(self):
        org_views = [
            'announcements/all_announcements',
            'announcements/notifications',
        ]
        self.invalidate_views(org_views, name="orgs")

    def invalidate_orgs(self):
        org_views = [
            'orgs/by_name',
            'orgs/org_requests',
            'orgs/team_by_domain',
            'orgs/team_by_org_and_name',
        ]
        self.invalidate_views(org_views, name="orgs")

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
