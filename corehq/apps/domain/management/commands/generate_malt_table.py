from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData
from dimagi.utils.dates import DateSpan, safe_strftime

import csv
import dateutil


class Command(BaseCommand):
    help = 'Generate MALT table for given month'
    args = '<month_year>'

    def write_data(self, csv_writer):
        start_date = self.datespan.startdate
        end_date = self.datespan.enddate

        for domain in Domain.get_all():
            for user in domain.all_users():
                forms = FormData.objects.exclude(device_id=COMMCONNECT_DEVICE_ID).filter(
                    user_id=user._id,
                    domain=domain.name,
                    received_on__range=(start_date, end_date)
                )
                num_of_forms = forms.count()
                is_web_user = user.doc_type == 'WebUser'
                apps_submitted_for = forms.values_list('app_id').distinct()
                apps_submitted_for = [app_id for (app_id,) in apps_submitted_for]

                for app_id in apps_submitted_for:
                    wam, pam = self._wam_pams(app_id)
                    row = [
                        user._id,
                        user.username,
                        user.email,
                        app_id,
                        is_web_user,
                        str(start_date),
                        domain.name,
                        num_of_forms,
                        wam,
                        pam
                    ]
                    csv_writer.writerow(row)

    @classmethod
    def _wam_pams(cls, app_id):
        # cache per domain
        # Todo. Handle deleted app and failure
        app = Application.get(app_id)
        return (getattr(app, 'amplifies_workers', 'not_set'),
                getattr(app, 'amplifies_project', 'not_set'))

    def handle(self, *args, **options):
        # Report is required only for June 2015, add cmd option latter, if required
        month_year = dateutil.parser.parse(args[0])
        self.datespan = DateSpan.from_month(month_year.month, month_year.year)
        # ToDo - remove following after testing
        # start_date = datetime.date(2014, 1, 1)
        # end_date = datetime.date(2015, 6, 1)
        file_name = 'MALT-table-{}.csv'.format(safe_strftime(month_year, '%b-%Y'))

        with open(file_name, 'wb+') as csvfile:
            csv_writer = csv.writer(
                csvfile,
                delimiter=',',
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL
            )
            print "Generating MALT table now..."
            csv_writer.writerow([
                'user_id',
                'username ',
                'user_email',
                'app_id'
                'web_user',
                'domain',
                'month',
                '#forms',
                'Amplifies Worker',
                'Amplifies Program',
            ])

            self.write_data(csv_writer)

        print "Generated file called {}".format(file_name)

# ToDo
# dates as args
# Do it in Database
# cache per domain
# Tests
# Performance
