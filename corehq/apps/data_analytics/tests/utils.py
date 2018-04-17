from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.elastic import send_to_elasticsearch
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form


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
    send_to_elasticsearch('forms', form_pair.json_form)
