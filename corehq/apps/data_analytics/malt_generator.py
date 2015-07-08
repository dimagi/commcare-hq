from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData
from corehq.util.quickcache import quickcache

from django.db import IntegrityError


class MALTTableGenerator(object):
    """
        Populates SQL table with data for given datespan
        See .models.MALTRow
    """

    def __init__(self, datespan_object):
        self.datespan = datespan_object

    def build_table(self):

        for domain in Domain.get_all():
            malt_rows_to_save = []
            for user in domain.all_users():
                malt_rows_to_save.extend(self.get_malt_row_dicts(user, domain.name))
            self.save_to_db(malt_rows_to_save)

    def get_malt_row_dicts(self, user, domain_name):
        malt_row_dicts = []
        forms_query = self.get_forms_queryset(user._id, domain_name)
        num_of_forms = forms_query.count()
        apps_submitted_for = [app_id for (app_id,) in
                              forms_query.values_list('app_id').distinct()]

        for app_id in apps_submitted_for:
            wam, pam, is_app_deleted = self._app_data(domain_name, app_id)
            malt_dict = {
                'month': self.datespan.startdate,
                'user_id': user._id,
                'username': user.username,
                'email': user.email,
                'is_web_user': user.doc_type == 'WebUser',
                'domain_name': domain_name,
                'num_of_forms': num_of_forms,
                'app_id': app_id,
                'wam': wam,
                'pam': pam,
                'is_app_deleted': is_app_deleted,
            }
            malt_row_dicts.append(malt_dict)
        return malt_row_dicts

    @classmethod
    def save_to_db(cls, malt_rows_to_save):
        try:
            MALTRow.objects.bulk_create(
                [MALTRow(**malt_dict) for malt_dict in malt_rows_to_save]
            )
        except IntegrityError:
            # no update_or_create in django-1.6
            for malt_dict in malt_rows_to_save:
                try:
                    unique_field_dict = {k: v
                                         for (k, v) in malt_dict.iteritems()
                                         if k in MALTRow.get_unique_fields()}
                    prev_obj = MALTRow.objects.get(**unique_field_dict)
                    for k, v in malt_dict.iteritems():
                        setattr(prev_obj, k, v)
                    prev_obj.save()
                except MALTRow.DoesNotExist:
                    MALTRow(**malt_dict).save()

    def get_forms_queryset(self, user_id, domain_name):
        start_date = self.datespan.startdate
        end_date = self.datespan.enddate

        return FormData.objects.exclude(device_id=COMMCONNECT_DEVICE_ID).filter(
            user_id=user_id,
            domain=domain_name,
            received_on__range=(start_date, end_date)
        )

    @classmethod
    @quickcache(['domain', 'app_id'])
    def _app_data(cls, domain, app_id):

        app = Application.get(app_id)
        return (getattr(app, 'amplifies_workers', 'not_set'),
                getattr(app, 'amplifies_project', 'not_set'),
                app.is_deleted())
