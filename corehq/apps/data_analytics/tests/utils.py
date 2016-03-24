import uuid
from corehq.apps.sofabed.models import FormData


def save_to_analytics_db(domain, received, app, device, user_id, username):
    unused_args = {
        'time_start': received,
        'time_end': received,
        'duration': 1
    }
    FormData.objects.create(
        domain=domain,
        received_on=received,
        instance_id=uuid.uuid4().hex,
        app_id=app,
        device_id=device,
        user_id=user_id,
        username=username,
        **unused_args
    )


