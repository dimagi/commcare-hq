import logging

from corehq.apps.app_manager.const import AMPLIFIES_NOT_SET
from corehq.apps.app_manager.models import get_app
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData, MISSING_APP_ID
from corehq.util.quickcache import quickcache

from django.db import IntegrityError
from django.db.models import Count


logger = logging.getLogger('build_malt_table')
logger.setLevel(logging.INFO)


class MALTTableGenerator(object):
    """
        Populates SQL table with data for given list of monthly-datespans
        See .models.MALTRow
    """

    def __init__(self, datespan_object_list):
        self.monthspan_list = datespan_object_list

    def build_table(self):

        for domain in Domain.get_all():
            malt_rows_to_save = []
            logger.info("Building MALT for {}".format(domain.name))
            for user in domain.all_users():
                for monthspan in self.monthspan_list:
                    try:
                        malt_rows_to_save.extend(self._get_malt_row_dicts(user, domain.name, monthspan))
                    except Exception as ex:
                        logger.error("Failed to get rows for user {id}. Exception is {ex}".format
                                     (id=user._id, ex=str(ex)), exc_info=True)
            self._save_to_db(malt_rows_to_save, domain._id)

    def _get_malt_row_dicts(self, user, domain_name, monthspan):
        malt_row_dicts = []
        forms_query = self._get_forms_queryset(user._id, domain_name, monthspan)
        apps_submitted_for = forms_query.values('app_id').annotate(num_of_forms=Count('instance_id'))

        for app_row_dict in apps_submitted_for:
            app_id = app_row_dict['app_id']
            num_of_forms = app_row_dict['num_of_forms']
            try:
                wam, pam, is_app_deleted = self._app_data(domain_name, app_id)
            except Exception as ex:
                if app_id == MISSING_APP_ID:
                    wam, pam, is_app_deleted = AMPLIFIES_NOT_SET, AMPLIFIES_NOT_SET, False
                else:
                    logger.error("Failed to get rows for user {id}, app {app_id}. Exception is {ex}".format
                                 (id=user._id, app_id=app_id, ex=str(ex)), exc_info=True)
                    continue

            malt_dict = {
                'month': monthspan.startdate,
                'user_id': user._id,
                'username': user.username,
                'email': user.email,
                'is_web_user': user.doc_type == 'WebUser',
                'domain_name': domain_name,
                'num_of_forms': num_of_forms,
                'app_id': app_id,
                'wam': MALTRow.AMPLIFY_COUCH_TO_SQL_MAP.get(wam, MALTRow.NOT_SET),
                'pam': MALTRow.AMPLIFY_COUCH_TO_SQL_MAP.get(pam, MALTRow.NOT_SET),
                'is_app_deleted': is_app_deleted,
            }
            malt_row_dicts.append(malt_dict)
        return malt_row_dicts

    @classmethod
    def _save_to_db(cls, malt_rows_to_save, domain_id):
        try:
            MALTRow.objects.bulk_create(
                [MALTRow(**malt_dict) for malt_dict in malt_rows_to_save]
            )
        except IntegrityError:
            # no update_or_create in django-1.6
            for malt_dict in malt_rows_to_save:
                cls._update_or_create(malt_dict)
        except Exception as ex:
            logger.error("Failed to insert rows for domain with id {id}. Exception is {ex}".format(
                         id=domain_id, ex=str(ex)), exc_info=True)

    @classmethod
    def _update_or_create(cls, malt_dict):
        try:
            # try update
            unique_field_dict = {k: v
                                 for (k, v) in malt_dict.iteritems()
                                 if k in MALTRow.get_unique_fields()}
            prev_obj = MALTRow.objects.get(**unique_field_dict)
            for k, v in malt_dict.iteritems():
                setattr(prev_obj, k, v)
            prev_obj.save()
        except MALTRow.DoesNotExist:
            # create
            try:
                MALTRow(**malt_dict).save()
            except Exception as ex:
                logger.error("Failed to insert malt-row {}. Exception is {}".format(
                    str(malt_dict),
                    str(ex)
                ), exc_info=True)
        except Exception as ex:
            logger.error("Failed to insert malt-row {}. Exception is {}".format(
                str(malt_dict),
                str(ex)
            ), exc_info=True)

    def _get_forms_queryset(self, user_id, domain_name, monthspan):
        start_date = monthspan.startdate
        end_date = monthspan.enddate

        return FormData.objects.exclude(
            device_id=COMMCONNECT_DEVICE_ID,
        ).filter(
            user_id=user_id,
            domain=domain_name,
            received_on__range=(start_date, end_date)
        )

    @classmethod
    @quickcache(['domain', 'app_id'])
    def _app_data(cls, domain, app_id):
        app = get_app(domain, app_id)
        return (getattr(app, 'amplifies_workers', AMPLIFIES_NOT_SET),
                getattr(app, 'amplifies_project', AMPLIFIES_NOT_SET),
                app.is_deleted())
