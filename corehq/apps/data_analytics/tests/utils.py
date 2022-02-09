from corehq.apps.app_manager.const import AMPLIFIES_YES
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
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


class MaltEndToEndTestMixin(object):

    DOMAIN_NAME = "test"
    USERNAME = "malt-user"
    DEVICE_ID = "my_phone"

    @classmethod
    def setup_domain(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()

    @classmethod
    def setup_user(cls):
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****', None, None)
        cls.user.save()

    @classmethod
    def setup_app(cls):
        cls.app = Application.new_app(cls.DOMAIN_NAME, "app 1")
        cls.app.amplifies_workers = AMPLIFIES_YES
        cls.app.save()
        cls.app_id = cls.app._id

    def save_form_data(self, app_id, received_on):
        save_to_es_analytics_db(
            domain=self.DOMAIN_NAME,
            received_on=received_on,
            device_id=self.DEVICE_ID,
            user_id=self.user._id,
            app_id=app_id,
        )
