import datetime
from corehq.apps.users.models import CouchUser
from django.core.management import BaseCommand
from optparse import make_option


RUN_FIX = 'fix'


class Command(BaseCommand):
    help = ("Fix inconsistent email_opt_out records between "
            "54d4c141842886724df99e7c6975cedba442d2ff and "
            "dd295c2815037e2c63b82be6c43038eeb94d7cf2.  "
            "Takes YYYY MM DD as arguments")

    option_list = BaseCommand.option_list + (
        make_option('--%s' % RUN_FIX,
                    action='store_true',
                    default=False,
                    help=''),
    )

    def handle(self, *args, **options):
        run_fix = options.get(RUN_FIX, False)
        for user in CouchUser.all():
            doc_json = CouchUser.get_db().get(user.get_id)
            if (doc_json.get('doc_type', None) == 'WebUser'
                    and user.created_on >= datetime.datetime(
                        *[int(_) for _ in args[0:3]])):
                if user.email_opt_out:
                    if run_fix:
                        user.email_opt_out = False
                        user.save()
                        print ('fixed %s, created on %s'
                               % (user.get_id, user.created_on))
                    else:
                        print ('should fix %s, created on %s'
                               % (user.get_id, user.created_on))
