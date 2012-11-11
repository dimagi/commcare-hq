from django.contrib.auth.models import User
from django.core.management.base import NoArgsCommand
import os
from django.conf import settings
import simplejson
from django.core import serializers
from dimagi.utils import make_time
from corehq.apps.users.models import WebUser
from corehq.apps.groups.models import Group
from pact.management.commands.constants import PACT_DOMAIN, PACT_HP_GROUP_NAME, PACT_HP_GROUP_ID

exclude_usernames = ['isaac','ink2','godfrey','Ayesha']

def get_or_create_pact_group():
    group = Group.view("groups/by_name", key=[PACT_DOMAIN, PACT_HP_GROUP_NAME],  include_docs=True).first()
    if not group:
        group = Group(name=PACT_HP_GROUP_NAME, domain=PACT_DOMAIN, _id = PACT_HP_GROUP_ID)
        group.save()
    if not group.case_sharing:
        group.case_sharing = True
        group.save()
    return group

class Command(NoArgsCommand):
    help = "Create or update pact users from django to WebUsers"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        django_user_dump = []
        actors_json = []

        pact_hp_group = get_or_create_pact_group()
        with open(os.path.join(settings.FILEPATH, 'pact_actors_all.json'), 'r') as ain:
            actors_json = simplejson.loads(ain.read())

        actor_username_map = {}
        for actor in actors_json:
            username = actor.get('username', None)
            if username is not None:
                actor_username_map[username] = actor


        with open(os.path.join(settings.FILEPATH, 'pact_users_all.json'), 'r') as fin:
            all_users = simplejson.loads(fin.read())
            for json_user in all_users:
                djuser = list(serializers.deserialize('json', simplejson.dumps([json_user])))[0]
                old_user_id = json_user['pk']
                djuser.object.username = djuser.object.username.lower()
                username = djuser.object.username

                if actor_username_map.has_key(username):
                    actor = actor_username_map[username]
                    #for the actors now, walk their properties and add them to the WebUser
                    if actor['doc_type'] != 'CHWActor':
                        continue
                else:
                    continue



                if username =='admin':
                    continue

                print username
                print "\tuser email: %s" % djuser.object.email
                is_new = False
                if User.objects.filter(username=username).count() == 0:
                    djuser.object.id = None
                    print "\tSaving new to DB"
                    djuser.object.save()
                    is_new = True
                else:
                    print "\tUpdating"
                    del json_user['fields']['groups']
                    del json_user['fields']['user_permissions']
                    User.objects.filter(username=username).update(**json_user['fields'])

                saved_user = User.objects.get(username=username)
                print saved_user

                web_user = WebUser.from_django_user(saved_user)
                if web_user is None:
                    web_user = WebUser()
                    print "Created web user"

                web_user.sync_from_django_user(saved_user)
                web_user.created_on = make_time()
                print "syncing web user from file"
                web_user.add_domain_membership(PACT_DOMAIN)
                web_user.save()

                if actor_username_map.has_key(username):
                    actor = actor_username_map[username]
                    #for the actors now, walk their properties and add them to the WebUser
                    if actor['doc_type'] == 'CHWActor':
                        web_user.add_phone_number(actor['phone_number'].replace('@vtext.com', ''))
                        pact_hp_group.add_user(web_user._id)
                    web_user['old_user_id'] = old_user_id

                    web_user.save()
                else:
                    actor = None
                if actor:
                    print "\tactor email: %s" % actor['email']
                    print "\tActor Type: %s" % actor['doc_type']

                #rachel, ayana, others with full admin
                #chws with just report viewing/edit data




