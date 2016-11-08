from corehq.apps.users.models import CommCareUser
from corehq.util.celery_utils import hqtask


@hqtask(queue='background_queue', ignore_result=True)
def create_user_cases(domain_name):
    from corehq.apps.callcenter.utils import sync_usercase
    for user in CommCareUser.by_domain(domain_name):
        sync_usercase(user)
