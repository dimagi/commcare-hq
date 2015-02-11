import uuid
from celery.task import task
from corehq.apps.hqcase.utils import submit_case_blocks, make_creating_casexml
from corehq.apps.users.models import CommCareUser
from casexml.apps.case.models import CommCareCase
from soil import DownloadBase


@task
def explode_case_task(user_id, domain, factor):
    user = CommCareUser.get_by_user_id(user_id, domain)
    keys = [[domain, owner_id, False] for owner_id in user.get_owner_ids()]
    messages = list()
    DownloadBase.set_progress(explode_case_task, 0, 0)
    count = 0

    for case in CommCareCase.view('hqcase/by_owner',
                                  keys=keys,
                                  include_docs=True,
                                  reduce=False):
        for i in range(factor - 1):
            new_case_id = uuid.uuid4().hex
            case_block, attachments = make_creating_casexml(case, new_case_id)
            submit_case_blocks(case_block, domain, attachments=attachments)
            DownloadBase.set_progress(explode_case_task, count + 1, 0)

    messages.append("All of %s's cases were exploded by a factor of %d" % (user.raw_username, factor))

    return {'messages': messages}
