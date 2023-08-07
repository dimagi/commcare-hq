from unittest.mock import patch
from corehq.apps.es.forms import form_adapter
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form


def save_to_es_analytics_db(domain, received_on, app_id, device_id, user_id, username=None):
    # Calling tests should ensure that xforms index exist
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
    with patch('corehq.pillows.utils.get_user_type', return_value='CommCareUser'):
        form_adapter.index(form_pair.json_form, refresh=True)
