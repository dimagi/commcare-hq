import uuid
from corehq.apps.sofabed.models import FormData
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.xform import XFormPillow
from corehq.util.test_utils import make_es_ready_form


def save_to_analytics_db(domain, received_on, app_id, device_id, user_id, username=None):
    unused_args = {
        'time_start': received_on,
        'time_end': received_on,
        'duration': 1
    }
    FormData.objects.create(
        domain=domain,
        received_on=received_on,
        instance_id=uuid.uuid4().hex,
        app_id=app_id,
        device_id=device_id,
        user_id=user_id,
        username=username,
        **unused_args
    )


def save_to_es_analytics_db(domain, received_on, app_id, device_id, user_id, username=None):
    metadata = TestFormMetadata(
        domain=domain,
        time_end=received_on,
        received_on=received_on,
        app_id=app_id,
        user_id=user_id,
        device_id=device_id,
        username=username

    )
    form_pair = make_es_ready_form(metadata)
    pillow = XFormPillow()
    pillow.change_transport(form_pair.json_form)
