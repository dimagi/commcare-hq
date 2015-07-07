from django.db import transaction

from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData


class MALTTableGenerator(object):
    """
        Populates SQL table with data for given datespan
        See MALTRow
    """
    _wam_pam_cache = {}

    def __init__(self, datespan_object):
        self.datespan = datespan_object

    @transaction.atomic
    def build_table(self):

        for domain in Domain.get_all():
            for user in domain.all_users():
                forms_query = self.get_forms_queryset(user._id, domain.name)
                num_of_forms = forms_query.count()
                apps_submitted_for = [app_id for (app_id,) in
                                      forms_query.values_list('app_id').distinct()]

                for app_id in apps_submitted_for:
                    wam, pam = self._wam_pams(domain.name, app_id)
                    db_row = MALTRow(
                        month=self.datespan.startdate,
                        user_id=user._id,
                        username=user.username,
                        email=user.email,
                        is_web_user=user.doc_type == 'WebUser',
                        domain_name=domain.name,
                        num_of_forms=num_of_forms,
                        app_id=app_id,
                        wam=wam,
                        pam=pam
                    )
                    db_row.save()
            self._destroy_wam_pam_cache(domain.name)

    def get_forms_queryset(self, user_id, domain_name):
        start_date = self.datespan.startdate
        end_date = self.datespan.enddate

        return FormData.objects.exclude(device_id=COMMCONNECT_DEVICE_ID).filter(
            user_id=user_id,
            domain=domain_name,
            received_on__range=(start_date, end_date)
        )

    @classmethod
    def _wam_pams(cls, domain, app_id):
        if (domain in cls._wam_pam_cache and
                app_id in cls._wam_pam_cache[domain]):
            return cls._wam_pam_cache[domain][app_id]

        elif domain not in cls._wam_pam_cache:
            cls._wam_pam_cache[domain] = {}

        app = Application.get(app_id)
        wam, pam = (getattr(app, 'amplifies_workers', 'not_set'),
                    getattr(app, 'amplifies_project', 'not_set'))
        cls._wam_pam_cache[domain][app_id] = (wam, pam)
        return wam, pam

    @classmethod
    def _destroy_wam_pam_cache(cls, domain):
        if domain in cls._wam_pam_cache:
            del cls._wam_pam_cache[domain]
