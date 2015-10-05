from django.conf import settings

import mailchimp
from corehq.apps.registration.utils import subscribe_user_to_mailchimp_list
from corehq.apps.users.models import WebUser
from django.core.management import BaseCommand
from optparse import make_option

RUN_FIX = 'subscribe'


class Command(BaseCommand):
    help = 'Subscribe old mass email list to mailchimp mass email list.'

    option_list = BaseCommand.option_list + (
        make_option('--%s' % RUN_FIX,
                    action='store_true',
                    default=False,
                    help=''),
    )

    def handle(self, *args, **options):
        for user_data in WebUser.view('users/mailing_list_emails').all():
            email_address = user_data['key']
            if options.get(RUN_FIX, False):
                print 'subscribing %s' % email_address
                try:
                    subscribe_user_to_mailchimp_list(
                        WebUser.get(user_data['id']),
                        settings.MAILCHIMP_MASS_EMAIL_ID,
                        email=email_address,
                    )
                    print 'subscribed %s' % email_address
                except mailchimp.ListAlreadySubscribedError:
                    print 'already subscribed %s' % email_address
                except mailchimp.ListInvalidImportError as e:
                    print e.message
                except mailchimp.ValidationError as e:
                    print e.message
                except mailchimp.Error as e:
                    raise e
            else:
                print 'ready to subscribe %s' % email_address
