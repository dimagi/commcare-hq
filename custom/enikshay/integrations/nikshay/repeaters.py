from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.models import CaseRepeater
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import NIKSHAY_INTEGRATION
from casexml.apps.case.xml.parser import CaseUpdateAction
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.repeaters.signals import create_repeat_records
from custom.enikshay.case_utils import get_person_case_from_episode
from custom.enikshay.exceptions import NikshayLocationNotFound
from custom.enikshay.const import TREATMENT_OUTCOME, EPISODE_PENDING_REGISTRATION
from custom.enikshay.integrations.ninetyninedots.repeaters import case_properties_changed
from custom.enikshay.integrations.nikshay.field_mappings import treatment_outcome


class NikshayRegisterPatientRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patients to Nikshay (episode case type)")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import RegisterNikshayPatientRepeaterView
        return reverse(RegisterNikshayPatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        # When case property episode.episode_pending_registration transitions from 'yes' to 'no',
        # and (episode.nikshay_registered != 'true'  or episode.nikshay_id != '')
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
            not episode_case_properties.get('nikshay_id', False) and
            case_properties_changed(episode_case, [EPISODE_PENDING_REGISTRATION]) and
            episode_case_properties.get(EPISODE_PENDING_REGISTRATION, 'yes') == 'no' and
            not test_submission(episode_case)
        )


class NikshayTreatmentOutcomeRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    friendly_name = _("Forward Treatment Outcomes to Nikshay (episode case type)")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayTreatmentOutcomesView
        return reverse(NikshayTreatmentOutcomesView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
            not episode_case_properties.get('nikshay_id', False) and
            case_properties_changed(episode_case, [TREATMENT_OUTCOME]) and
            episode_case_properties.get(TREATMENT_OUTCOME) in treatment_outcome.keys()
        )


def test_submission(episode_case):
    person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )
    return phi_location.metadata.get('is_test', "yes") == "yes"


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)
    create_repeat_records(NikshayTreatmentOutcomeRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
