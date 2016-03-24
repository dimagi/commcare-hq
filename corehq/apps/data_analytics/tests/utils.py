import uuid
from corehq.apps.sofabed.models import FormData


def save_to_analytics_db(domain, received_on, app_id, device_id, user_id, username=None, instance_id=None):
    unused_args = {
        'time_start': received_on,
        'time_end': received_on,
        'duration': 1
    }
    instance_id = instance_id or uuid.uuid4().hex
    FormData.objects.create(
        domain=domain,
        received_on=received_on,
        instance_id=instance_id,
        app_id=app_id,
        device_id=device_id,
        user_id=user_id,
        username=username,
        **unused_args
    )
