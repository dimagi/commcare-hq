from django.core.management.base import LabelCommand, CommandError
import os
from couchforms.models import XFormInstance
from corehq.apps.users.util import format_username
from dimagi.utils.couch.database import get_db

# This management command was broken by the user refactor
class Command(LabelCommand):
    help = "Goes through and changes meta.userID to match the UUID for the user given by meta.username and the domain"
    args = ""
    label = ""

    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Usage: manage.py submit_forms <domain>')
        domain = args[0]
        submissions = XFormInstance.view('reports/all_submissions', startkey=[domain], endkey=[domain, {}], include_docs=True)
        ids_by_username = dict()
        def get_id(username):
            if username in ids_by_username:
                return ids_by_username[username]
            else:
                userID = get_db().view('users/logins_by_username', key=username).one()
                userID = userID['value'] if userID else None
                ids_by_username[username] = userID
                return userID
        for submission in submissions:
            if 'meta' in submission.form:
                username = format_username(submission.form['meta']['username'], domain)
                userID = get_id(username)
                if userID:
                    submission.form['meta']['userID'] = userID
                    submission.save()
                print submission._id, username, userID
            else:
                print "skipped: %s" % submission._id

