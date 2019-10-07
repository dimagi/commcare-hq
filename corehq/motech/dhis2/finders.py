from collections import namedtuple
from functools import partial

from memoized import memoized_property

from corehq.motech.dhis2.const import DHIS2_API_VERSION
from corehq.motech.finders import MATCH_FUNCTIONS, MATCH_TYPE_EXACT

CandidateScore = namedtuple('CandidateScore', 'candidate score')


class TrackedEntityInstanceFinder:

    def __init__(self, requests, case_config):
        self.requests = requests
        self.case_config = case_config

    @property
    def property_weights(self):
        return self.case_config.finder_config.property_weights

    @property
    def confidence_margin(self):
        return self.case_config.finder_config.confidence_margin

    @memoized_property
    def attr_type_id_value_source_by_case_property(self):
        return {
            value_source["case_property"]: (attr_type_id, value_source)
            for attr_type_id, value_source in self.case_config.attributes.items()
        }

    def find_tracked_entity_instances(self, case_trigger_info):
        """
        Search DHIS2 for potential matches of the CommCare case. Score
        search results and keep those with score > 1. If more than one
        result has a score > 1, select the best candidate if it exceeds
        a confidence margin. Otherwise return all results with score > 1.
        """
        results = self.fetch_query_results(case_trigger_info)
        candidate_scores = []
        for instance in results:
            score = self.get_score(instance, case_trigger_info)
            if score >= 1:
                candidate_scores.append(CandidateScore(instance, score))

        if len(candidate_scores) > 1:
            candidate_scores = sorted(candidate_scores, key=lambda cs: cs.score, reverse=True)
            if candidate_scores[0].score / candidate_scores[1].score > 1 + self.confidence_margin:
                return [candidate_scores[0].candidate]
        return [cs.candidate for cs in candidate_scores]

    def fetch_query_results(self, case_trigger_info):
        endpoint = f"/api/{DHIS2_API_VERSION}/trackedEntityInstances"
        query_filters = self.get_query_filters(case_trigger_info)
        if not query_filters:
            return []
        params = {
            "ou": self.case_config.org_unit_id.get_value(case_trigger_info),
            "filter": query_filters,
            "ouMode": "DESCENDANTS",
            "skipPaging": "true",
        }
        response = self.requests.get(endpoint, params=params, raise_for_status=True)
        return response.json()["trackedEntityInstances"]

    def get_query_filters(self, case_trigger_info):
        filters = []
        for property_weight in self.property_weights:
            case_property = property_weight['case_property']
            value = case_trigger_info.extra_fields[case_property]
            if property_weight["match_type"] == MATCH_TYPE_EXACT and is_a_value(value):
                attr_type_id = self.attr_type_id_value_source_by_case_property[case_property][0]
                filters.append(f"{attr_type_id}:EQ:{value}")
        return filters

    def get_score(self, candidate, case_trigger_info):
        return sum(self.get_weights(candidate, case_trigger_info))

    def get_weights(self, candidate, case_trigger_info):
        for property_weight in self.property_weights:
            case_property = property_weight['case_property']
            (attr_type_id, value_source) = self.attr_type_id_value_source_by_case_property[case_property]

            candidate_value = get_tei_attr(candidate, attr_type_id)
            case_value = case_trigger_info.extra_fields[case_property]

            weight = property_weight['weight']
            match_type = property_weight['match_type']
            match_params = property_weight['match_params']
            match_function = partial(MATCH_FUNCTIONS[match_type], *match_params)
            is_equivalent = match_function(value_source.deserialize(candidate_value), case_value)
            yield weight if is_equivalent else 0


def get_tei_attr(instance, attr_type_id):
    for attr in instance["attributes"]:
        if attr["attribute"] == attr_type_id:
            return attr["value"]


def is_a_value(value):
    """
    Returns True if `value` is truthy or 0

    >>> is_a_value("yes")
    True
    >>> is_a_value(0)
    True
    >>> is_a_value("")
    False

    """
    return bool(value or value == 0)
