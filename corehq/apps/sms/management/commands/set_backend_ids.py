from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.sms.mixin import VerifiedNumber


class Command(BaseCommand):
    args = 'domain [backend_id] [--test]'
    help = ('Updates the backend_id on all VerifiedNumber entries for the '
        'given domain. If backend_id is not specified, it is set to None. '
        'VerifiedNumbers belonging to cases are not processed as the '
        'contact_backend_id case property must be updated to properly '
        'reflect that.')
    option_list = BaseCommand.option_list + (
        make_option('--test',
                    action='store_true',
                    dest='test',
                    default=False,
                    help=('Include this option to only print the backend_id '
                          'discrepancies and not update them.')),
    )

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError('Usage: python manage.py set_backend_ids domain [backend_id] [--test]')

        domain = args[0]
        if len(args) > 1:
            backend_id = args[1]
        else:
            backend_id = None

        test_only = options['test']

        for vn in VerifiedNumber.by_domain(domain):
            if (not vn.backend_id) and (not backend_id):
                pass
            elif vn.backend_id == backend_id:
                pass
            elif test_only:
                print '%s %s, number %s has backend %s instead of %s' % \
                    (vn.owner_doc_type, vn.owner_id, vn.phone_number,
                     'None' if vn.backend_id is None else "'%s'" % vn.backend_id, backend_id)
            else:
                if vn.owner_doc_type == "CommCareCase":
                    print 'Cannot update backend_id for %s because it is a case' % vn.owner_id
                else:
                    print 'Updating backend_id from %s to %s for %s %s, number %s' % \
                        (vn.backend_id, backend_id, vn.owner_doc_type, vn.owner_id, vn.phone_number)
                    vn.backend_id = backend_id
                    vn.save()
