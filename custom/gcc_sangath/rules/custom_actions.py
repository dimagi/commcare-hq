from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.hqcase.utils import update_case, AUTO_UPDATE_XMLNS
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from custom.gcc_sangath.const import (
    DATE_OF_PEER_REVIEW_CASE_PROP,
    MEAN_GENERAL_SKILLS_SCORE_CASE_PROP,
    MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP,
    NEEDS_AGGREGATION_CASE_PROP,
    NEEDS_AGGREGATION_NO_VALUE,
    PEER_RATING_CASE_TYPE,
    SESSION_CASE_TYPE,
    SESSION_RATING_CASE_PROP,
)


def sanitize_session_peer_rating(session_case, rule):
    """
    For any session case
    sanitize the peer_rating metrics based on child cases of type peer_rating
    """
    if session_case.type != SESSION_CASE_TYPE:
        return CaseRuleActionResult()

    peer_rating_cases = _get_peer_rating_cases(session_case)
    num_updates = 0

    if peer_rating_cases:
        case_updates = _get_case_updates(peer_rating_cases)
        (submission, cases) = update_case(
            session_case.domain,
            session_case.case_id,
            case_properties=case_updates,
            xmlns=AUTO_UPDATE_XMLNS,
            device_id=__name__ + ".sanitize_session_peer_rating",
            form_name=rule.name,
        )
        num_updates = 1
        rule.log_submission(submission.form_id)

    return CaseRuleActionResult(
        num_updates=num_updates,
    )


def _get_peer_rating_cases(session_case):
    case_ids = CommCareCaseIndex.objects.get_extension_case_ids(session_case.domain, [session_case.case_id])
    extension_cases = CommCareCase.objects.get_cases(case_ids, session_case.domain)
    peer_rating_cases = [case for case in extension_cases if case.type == PEER_RATING_CASE_TYPE]
    return peer_rating_cases


def _get_case_updates(peer_rating_cases):
    number_of_peer_ratings = len(peer_rating_cases)
    sum_of_session_rating = _get_sum(SESSION_RATING_CASE_PROP, peer_rating_cases)

    agg_of_mean_treatment_specific_score = _get_aggregate(MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP,
                                                          peer_rating_cases)
    agg_of_mean_general_skills_score = _get_aggregate(MEAN_GENERAL_SKILLS_SCORE_CASE_PROP, peer_rating_cases)

    latest_peer_review = _get_latest_peer_review_date(peer_rating_cases)

    case_updates = dict({
        'feedback_num': number_of_peer_ratings,
        'total_session_rating': sum_of_session_rating,
        'agg_rating': round(sum_of_session_rating / number_of_peer_ratings, 1),
        'agg_mean_treatment_specific_score': agg_of_mean_treatment_specific_score,
        'agg_mean_general_skills_score': agg_of_mean_general_skills_score,
        'date_of_peer_review': latest_peer_review,
        'share_score_check': 'yes',
    })
    case_updates[NEEDS_AGGREGATION_CASE_PROP] = NEEDS_AGGREGATION_NO_VALUE
    return case_updates


def _get_sum(case_property, peer_rating_cases):
    total = sum([
        float(peer_rating_case.get_case_property(case_property) or 0)
        for peer_rating_case in peer_rating_cases
    ])
    return float("{:.1f}".format(total))


def _get_aggregate(case_property, peer_rating_cases):
    total = _get_sum(case_property, peer_rating_cases)
    count = len(peer_rating_cases)
    return float("{:.1f}".format(total / count))


def _get_latest_peer_review_date(peer_rating_cases):
    latest_peer_review = None
    for peer_rating_case in peer_rating_cases:
        date_of_peer_review = peer_rating_case.get_case_property(DATE_OF_PEER_REVIEW_CASE_PROP)
        if not latest_peer_review and date_of_peer_review:
            latest_peer_review = date_of_peer_review
        elif latest_peer_review and date_of_peer_review and date_of_peer_review > latest_peer_review:
            latest_peer_review = date_of_peer_review
    return latest_peer_review
