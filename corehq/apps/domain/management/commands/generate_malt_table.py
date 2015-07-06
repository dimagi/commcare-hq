from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData

import csv
import datetime


class Command(BaseCommand):
    help = 'Generate malt table for June 2015'

    def write_data(self, csv_writer, start_date, end_date):
        for domain in Domain.get_all():
            for user in domain.all_users():
                forms = FormData.objects.exclude(device_id=COMMCONNECT_DEVICE_ID).filter(
                    user_id=user._id,
                    domain=domain.name,
                    received_on__range=(start_date, end_date)
                )
                num_of_forms = forms.count()
                apps_submitted_for = forms.values_list('app_id').distinct()
                apps_submitted_for = [app_id for (app_id,) in apps_submitted_for]
                wam_eligible = self._wam_app_in_list(apps_submitted_for)
                is_web_user = user.doc_type == 'WebUser'
                row = [
                    user._id,
                    user.username,
                    user.email,
                    is_web_user,
                    str(start_date),
                    domain.name,
                    num_of_forms,
                    wam_eligible
                ]
                csv_writer.writerow(row)

    @classmethod
    def _wam_app_in_list(cls, app_ids):
        """
        Given list of app_ids returns following
        - 'true' if at least one app has 'amplifies_workers' set to 'yes'
        - 'false' if none of the apps has 'amplifies_workers' set to 'yes' and
                     at least one app has 'amplifies_workers' set to 'no'
        - 'na' if all apps have 'amplifies_workers' set to 'not_set'
        """

        to_return = 'na'
        for app_id in app_ids:
            wam_eligible = cls._wam_eligible_app(app_id)
            if wam_eligible == 'yes':
                to_return = 'true'
                break
            elif wam_eligible.bool_value == 'no':
                to_return = 'false'
            elif wam_eligible.bool_value == 'not_set':
                continue
        return to_return

    @classmethod
    def _wam_eligible_app(cls, app_id):
        # cache per domain
        # Todo. Handle deleted app and failure
        app = Application.get(app_id)
        wam_eligible = getattr(app, 'amplifies_workers', 'not_set')

        return wam_eligible

    def handle(self, *args, **options):
        # Report is required only for June 2015, add cmd option latter, if required
        start_date = datetime.date(2015, 6, 1)
        end_date = datetime.date(2015, 6, 30)

        file_name = 'MALT-table-{}.csv'.format(str(start_date))

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
                'web_user',
                'domain',
                'month',
                '#forms',
                'WAM Eligible',
            ])

            self.write_data(csv_writer, start_date, end_date)

        print "Generated file called {}".format(file_name)
        # ToDo - remove following after testing
        # start_date = datetime.date(2014, 1, 1)
        # end_date = datetime.date(2015, 6, 1)
        # csv_writer = None
