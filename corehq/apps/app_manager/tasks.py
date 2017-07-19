from django.utils.translation import ugettext as _

from celery.task import task
from corehq.apps.users.models import CommCareUser
from corehq.util.decorators import serial_task


@task(queue='background_queue', ignore_result=True)
def create_user_cases(domain_name):
    from corehq.apps.callcenter.utils import sync_usercase
    for user in CommCareUser.by_domain(domain_name):
        sync_usercase(user)


@serial_task('{app._id}-{app.version}', max_retries=0, timeout=60*60)
def make_async_build(app, username):
    latest_build = app.get_latest_app(released_only=False)
    if latest_build.version == app.version:
        return
    errors = app.validate_app()
    if not errors:
        copy = app.make_build(
            previous_version=latest_build,
            comment=_('Auto-generated by a phone update from {}'.format(username))
        )
        copy.save(increment_version=False)
