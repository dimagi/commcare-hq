from celery.task import task
from celery.utils.log import get_task_logger

from dimagi.utils.couch.database import iter_docs

from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import update_user_in_es

logger = get_task_logger(__name__)


@task(queue='background_queue', ignore_result=True)
def refresh_es_for_profile_users(domain, profile_id):
    try:
        profile = CustomDataFieldsProfile.objects.get(id=profile_id, definition__domain=domain)
    except CustomDataFieldsProfile.DoesNotExist:
        return

    for user_doc in iter_docs(CouchUser.get_db(), profile.user_ids_assigned()):
        update_user_in_es(None, CouchUser.wrap_correctly(user_doc))
