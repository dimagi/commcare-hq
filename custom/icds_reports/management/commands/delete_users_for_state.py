from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from custom.icds_reports.models.views import AwcLocationMonths
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation


class Command(BaseCommand):

    def get_location_ids(self, loaction_obj):
        state_ids = set([location.state_id for location in loaction_obj])
        district_ids = set([location.district_id for location in loaction_obj])
        block_ids = set([location.block_id for location in loaction_obj])
        supervisor_ids = set([location.supervisor_id for location in loaction_obj])
        awc_ids = set([location.awc_id for location in loaction_obj])
        return state_ids,district_ids,block_ids, supervisor_ids, awc_ids

    def handle(self, *args, **kwargs):
        telangana_locations = AwcLocationMonths.objects.filter(state_name='Telangana', aggregation_level=5)
        state_ids, district_ids, block_ids, supervisor_ids, awc_ids = self.get_location_ids(telangana_locations)

        all_locations = state_ids | district_ids | block_ids | supervisor_ids | awc_ids

        location_users = list()
        user_submitted_forms = []
        for loc in all_locations:
            users_to_delete = get_users_by_location_id('icds-cas', loc).all()

            for user in users_to_delete:
                if user.reporting_metadata.sync_time is None:
                    if (user.user_location_id and
                            SQLLocation.objects.get_or_None(location_id=user.user_location_id,
                                                            user_id=user._id)):
                        location_users.append(user)
                    else:
                        if not user.reporting_metadata.last_submission_for_user.submission_date and\
                                not user.reporting_metadata.last_sync_for_user.sync_date:
                            user.retire()
                        else:
                            user_submitted_forms.append(user)

        for loc in all_locations:
            location = SQLLocation.objects.get_or_None(location_id=loc)
            if location:
                location.full_delete()

        for user in location_users:
            user.retire()

        print("These users submitted the forms")
        print(user_submitted_forms)


