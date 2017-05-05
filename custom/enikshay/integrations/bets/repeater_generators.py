import json
from corehq.apps.api.resources.v0_5 import CommCareUserResource
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay.integrations.bets.repeaters import (
    BETSUserRepeater,
    BETSLocationRepeater,
)


@RegisterGenerator(BETSUserRepeater, "user_json", "JSON", is_default=True)
class BETSUserPayloadGenerator(BasePayloadGenerator):

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, user):
        resource = CommCareUserResource(api_name='v0.5')
        bundle = resource.build_bundle(obj=user)
        return resource.full_dehydrate(bundle).data


@RegisterGenerator(BETSLocationRepeater, "user_json", "JSON", is_default=True)
class BETSLocationPayloadGenerator(BasePayloadGenerator):

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, location):
        return location.to_json()
