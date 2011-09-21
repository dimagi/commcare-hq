from django.core.management.base import LabelCommand
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import ReportNotification
from corehq.apps.sms.models import MessageLog
from corehq.apps.users import old_couch_user_models
from corehq.apps.users.models import CouchUser

class Command(LabelCommand):
    help = "Migrates users from old user model of Dec. 2010 to new WebUser/CommCareUser model of Aug. 2011"
    args = ""
    label = ""

    def handle(self, *args, **options):
        old_couch_users = old_couch_user_models.CouchUser.view('users/old_users', include_docs=True)
        print "Loaded all (old) CouchUser docs into memory."
        for old_couch_user in old_couch_users:
            try:
                couch_user = CouchUser.from_old_couch_user(old_couch_user)
                couch_user.old_couch_user_id = old_couch_user.get_id
                couch_user.save(force_update=True)
            except Exception as e:
                print "There was an error migrating CouchUser with _id %s: %s" % (
                    old_couch_user._id.encode('utf-8'),
                    str(e)
                )
            else:
                print "Migrated %s (%s)" % (couch_user.username.encode('utf-8'), couch_user.user_id.encode('utf-8'))

        print "Creating old => new user _id map"
        couch_users = CouchUser.all()
        id_map = {}
        for couch_user in couch_users:
            try:
                old_id = couch_user.old_couch_user_id
            except KeyError:
                pass
            else:
                id_map[old_id] = couch_user.user_id
            try:
                couch_user.save()
            except Exception as e:
                print 'Failed to save %s: %s' % (couch_user.user_id.encode('utf-8'), str(e))

        print "Cleaning up references..."

        print "* Group"
        group_ids = set()
        for group in Group.view('groups/by_user', keys=id_map.keys(), include_docs=True):
            if group._id in group_ids:
                continue
            for i, user_id in enumerate(group.users):
                if user_id in id_map:
                    group.users[i] = id_map[user_id]
            group.save()
            group_ids.add(group._id)

        print "* ReportNotification"
        notification_ids = set()
        for notification in ReportNotification.view('reports/user_notifications',
                                                    keys=id_map.keys(),
                                                    include_docs=True):
            if notification._id in notification_ids:
                continue
            for i, user_id in enumerate(notification.user_ids):
                if user_id in id_map:
                    notification.user_ids[i] = id_map[user_id]
            notification.save()
            notification_ids.add(notification._id)

        print "* MessageLog"
        messages = MessageLog.objects.all()
        count = 0
        for message in messages:
            if message.couch_recipient in id_map:
                message.couch_recipient = id_map[message.couch_recipient]
                count += 1
        print "    %s/%s changed (just in case you were curious)" % (count, messages.count())