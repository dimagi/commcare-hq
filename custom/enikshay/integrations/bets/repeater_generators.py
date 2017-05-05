import json
from corehq.apps.api.resources.v0_5 import CommCareUserResource
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay.integrations.bets.repeaters import (
    UserRepeater,
)


@RegisterGenerator(UserRepeater, "user_json", "JSON", is_default=True)
class UserPayloadGenerator(BasePayloadGenerator):

    @property
    def content_type(self):
        return 'application/json'

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            # TODO
            print "FAILURE"

    def handle_failure(self, response, case, repeat_record):
        if 400 <= response.status_code <= 500:
            # TODO
            print "FAILURE"

    def get_test_payload(self, domain):
        return json.dumps({
            'username': "somethingclever@{}.commcarehq.org".format(domain),
        })

    def get_payload(self, repeat_record, user):
        resource = CommCareUserResource(api_name='v0.5')
        bundle = resource.build_bundle(obj=user)
        return resource.full_dehydrate(bundle).data
