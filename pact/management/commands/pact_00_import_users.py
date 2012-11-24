from django.contrib.auth.models import User
from django.core.management.base import NoArgsCommand
import simplejson
from django.core import serializers
from dimagi.utils import make_time
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.groups.models import Group
from localsettings import PACT_CHWS
from pact.management.commands import PactMigrateCommand
from pact.enums import PACT_DOMAIN, PACT_HP_GROUP_ID, PACT_HP_GROUPNAME
from pact.management.commands.constants import  PACT_URL


def get_or_create_pact_group():
    print "### Get or create pact hp group"
    group = Group.view("groups/by_name", key=[PACT_DOMAIN, PACT_HP_GROUPNAME],  include_docs=True).first()
    if group:
        Group.get_db().delete_doc(group['_id'])
        group=None

    if not group:
        group = Group(name=PACT_HP_GROUPNAME, domain=PACT_DOMAIN, _id=PACT_HP_GROUP_ID)
        group.save()
        print "\tpact group created"
    if not group.case_sharing:
        print "\tpact group loaded from DB"
        group.case_sharing = True
        group.save()
    print "\tretrieved pact group"
    return group

class Command(PactMigrateCommand):
    help = "Create or update pact users from django to WebUsers"
    option_list = NoArgsCommand.option_list + (
    )

    def handle_noargs(self, **options):

        self.get_credentials()

        pact_hp_group = get_or_create_pact_group()
        print "#### Getting actors json from server"
        actors_json = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/actors/'))

        actor_username_map = {}
        for actor in actors_json:
            username = actor.get('username', None)
            if username is not None:
                username = username.lower()
                actor_username_map[username] = actor
        print "#### actor json loaded from remote server"


        print "#### Retrieving django users from remote"
        all_users = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/users/'))
        print "django users retrieved: %d" % len(all_users)
#        all_users = simplejson.loads(users_json)
        for json_user in all_users:
            #this is nasty because the deserializer only does objects in an array vs just a
            # single instance, so we're loading json, then wrapping it into an array to the
            # django deserializer
            username = json_user['fields']['username'].lower()
            if username not in PACT_CHWS.keys():
                print "# skipping %s" % json_user['pk']
                continue

            if username =='admin':
                print "# skipping admin"
                continue

            djuser = list(serializers.deserialize('json', simplejson.dumps([json_user])))[0]
            old_user_id = json_user['pk']
            djuser.object.username = djuser.object.username.lower()

            if actor_username_map.has_key(username):
                actor = actor_username_map[username]
                #for the actors now, walk their properties and add them to the WebUser
                if actor['doc_type'] != 'CHWActor':
                    actor = None
            else:
                actor = None


            print "pact user: %s " % username
            print "\tuser email: %s" % djuser.object.email
            is_new = False
            if User.objects.filter(username=username).count() == 0:
                djuser.object.id = None
                print "\tSaving new to DB"
                djuser.object.save()
                is_new = True
            else:
                print "\tUpdating..."
                del json_user['fields']['groups']
                del json_user['fields']['user_permissions']
                User.objects.filter(username=username).update(**json_user['fields'])
            saved_user = User.objects.get(username=username)
            print "\tDjango user %s saved to HQ database" % username


            print "\tRecreating Couch User"
            couchusers = CouchUser.get_db().view('users/by_username', key=username,  include_docs=True).all()
            if len(couchusers) > 0:
                couchuser = couchusers[0]['doc']
                print "\t\tCouch User deleted - recreating"
                CouchUser.get_db().delete_doc(couchuser)


            #by default create a CommCareUser for everyone
            cc_user = CommCareUser.from_django_user(saved_user)
            if cc_user is None:
                cc_user = CommCareUser()
                cc_user.created_on = make_time()
                print "\tCreated web user"

            print "\tsyncing user from file, adding to %s domain as CommCareUser" % PACT_DOMAIN
            cc_user.sync_from_django_user(saved_user)
            cc_user.domain = PACT_DOMAIN
            #cc_user.add_domain_membership(PACT_DOMAIN)
            cc_user['old_user_id'] = old_user_id
            cc_user.save()
            pact_hp_group.add_user(cc_user._id)

            print "\tsyncing actor properties to web user"
            if actor_username_map.has_key(username):
                actor = actor_username_map[username]
                #for the actors now, walk their properties and add them to the WebUser
                if actor['doc_type'] == 'CHWActor':
                    print "\tchw actor found, updating phone number"
                    cc_user.add_phone_number(actor['phone_number'].replace('@vtext.com', ''))
                    cc_user.save()
            else:
                print "\t\tNo actor doc found"
                actor = None
            if actor:
                print "\tactor email: %s" % actor['email']
                print "\tActor Type: %s" % actor['doc_type']

            #rachel, ayana, others with full admin
            #chws with just report viewing/edit data




