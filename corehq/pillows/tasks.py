from datetime import timedelta

from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.es import FormES
from corehq.apps.es.aggregations import CardinalityAggregation
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.utils.xform import resave_form
from corehq.pillows.utils import get_user_type_deep_cache_for_unknown_users, UNKNOWN_USER_TYPE
from corehq.util.decorators import serial_task
from corehq.util.metrics import metrics_gauge
from corehq.util.metrics.const import MPM_MAX
from corehq.util.quickcache import quickcache


@periodic_task(run_every=timedelta(minutes=10))
@quickcache([], timeout=9 * 60)  # Protect from many runs after recovering from a backlog
def send_unknown_user_type_stats():
    metrics_gauge('commcare.fix_user_types.unknown_user_count',
                  _get_unknown_user_type_user_ids_approx_count(),
                  multiprocess_mode=MPM_MAX)
    metrics_gauge('commcare.fix_user_types.unknown_user_form_count',
                  FormES().user_type(UNKNOWN_USER_TYPE).count(),
                  multiprocess_mode=MPM_MAX)


@periodic_task(run_every=crontab(minute=0, hour=0))
def fix_user_types():
    unknown_user_ids = _get_unknown_user_type_user_ids()
    for user_id in unknown_user_ids:
        user_type = get_user_type_deep_cache_for_unknown_users(user_id)
        if user_type != UNKNOWN_USER_TYPE:
            resave_es_forms_with_unknown_user_type.delay(user_id)


@serial_task('{user_id}', queue='background_queue')
def resave_es_forms_with_unknown_user_type(user_id):
    domain_form_id_list = (
        FormES().user_type(UNKNOWN_USER_TYPE).user_id(user_id)
        .values_list('domain', '_id', scroll=True)
    )
    for domain, form_id in domain_form_id_list:
        form = FormAccessors(domain).get_form(form_id)
        resave_form(domain, form)


def _get_unknown_user_type_user_ids():
    return (FormES().user_type(UNKNOWN_USER_TYPE).user_aggregation().run()
            .aggregations.user.keys)


def _get_unknown_user_type_user_ids_approx_count():
    agg = CardinalityAggregation('users_count', 'form.meta.userID')
    return (FormES().user_type(UNKNOWN_USER_TYPE).aggregation(agg).run()
            .aggregations.users_count.value)
