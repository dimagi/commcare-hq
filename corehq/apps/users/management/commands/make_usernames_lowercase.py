from django.core.management import BaseCommand

from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Makes usernames into lowercase"

    def handle(self, *args, **options):
        all_usernames = set(
            map(
                lambda x: x['key'],
                CouchUser.get_db().view(
                    'users/by_username',
                    include_docs=False,
                    reduce=False,
                ).all()
            )
        )
        uppercase_usernames = filter(
            lambda username: any(char.isupper() for char in username),
            all_usernames
        )

        print 'Number of uppercase usernames: %d' % len(uppercase_usernames)

        for username in uppercase_usernames:
            print 'Making %s lowercase' % username
            if username.lower() not in all_usernames:
                user = CouchUser.get_by_username(username)
                user.username = username.lower()
                user.save()
            else:
                print '%s already exists' % username.lower()
