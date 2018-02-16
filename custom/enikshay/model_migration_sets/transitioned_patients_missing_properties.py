from __future__ import absolute_import
from custom.enikshay.case_utils import get_occurrence_case_from_episode
from custom.enikshay.exceptions import ENikshayCaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.decorators.memoized import memoized


class TransitionedPatientsMissingProperties(object):
    """https://manage.dimagi.com/default.asp?262154

    episode_treating_hospital and episode_fo on the episode were set on the
    incorrect episode when the transition episode form was filled.

    """
    def __init__(self, domain, person, episode):
        self.domain = domain
        self.person = person
        self.episode = episode

    def update_json(self):
        if not self.should_update:
            return {}

        return {
            'episode_treating_hospital': self.suspect_case.get_case_property('episode_treating_hospital'),
            'episode_fo': self.suspect_case.get_case_property('episode_fo')
        }

    @property
    def should_update(self):
        # for all "confirmed_tb" episodes, find all other episodes for that occurrence.
        # if there is a suspect episode, then this is
        # if the occurrence has more than one episode then the transition
        # patient form was filled out and this case should be updated
        if self.episode.get_case_property('episode_type') == 'presumptive_tb':
            return False

        if (self.episode.get_case_property('episode_treating_hospital') is not None
           and self.episode.get_case_property('episode_treating_hospital') != ''):
            return False

        if (self.episode.get_case_property('episode_fo') is not None
           and self.episode.get_case_property('episode_fo') != ''):
            return False

        if self.suspect_case:
            return True

        return False

    @property
    @memoized
    def suspect_case(self):
        try:
            occurrence = get_occurrence_case_from_episode(self.domain, self.episode.case_id)
        except ENikshayCaseNotFound:
            return False

        cases = CaseAccessors(self.domain).get_reverse_indexed_cases([occurrence.case_id])
        suspect_cases = [case for case in cases if
                         case.type == 'episode'
                         and case.get_case_property('episode_type') == 'presumptive_tb']

        if len(suspect_cases) == 1:
            return suspect_cases[0]
        else:
            # if there is more than one suspect case, also return None, since
            # that is an indeterminate case
            return None
