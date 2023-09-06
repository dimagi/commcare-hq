from corehq.apps.email.models import SQLEmailSMTPBackend
from corehq.messaging.emailbackends.aws.forms import AWSBackendForm


class AWSBackend(SQLEmailSMTPBackend):
    class Meta(object):
        app_label = 'email'

    @classmethod
    def get_api_id(cls):
        return 'AWS'

    @classmethod
    def get_generic_name(cls):
        return "AWS"

    @classmethod
    def get_available_extra_fields(cls):
        return []

    @classmethod
    def get_form_class(cls):
        return AWSBackendForm

    def get_extra_fields(self):
        result = {field: None for field in self.get_available_extra_fields()}
        return result

    def set_extra_fields(self, **kwargs):
        """
        Only updates the fields that are passed as kwargs, and leaves
        the rest untouched.
        """
        result = self.get_extra_fields()
        for k, v in kwargs.items():
            if k not in self.get_available_extra_fields():
                raise Exception(f"Field {k} is not an available extra field for {self.__class__.__name__}")
            result[k] = v

        self.extra_fields = result
