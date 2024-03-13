from corehq.apps.domain.management.commands.remove_duplicate_domains import score_domain_doc
from corehq.apps.domain.models import Domain


def test_score_domain_doc():
    # ceteris paribus, choose the current one
    score_1 = score_domain_doc(Domain(is_active=True, _rev='1-xxx'), is_currently_chosen=True)
    score_2 = score_domain_doc(Domain(is_active=True, _rev='1-xxx'), is_currently_chosen=False)
    assert score_1 > score_2

    # Choose a non-current one if it's better on both is_active and rev_count
    score_1 = score_domain_doc(Domain(is_active=False, _rev='1-xxx'), is_currently_chosen=True)
    score_2 = score_domain_doc(Domain(is_active=True, _rev='6-xxx'), is_currently_chosen=False)
    assert score_2 > score_1

    # Obviously choose the current one if it's better on all three fronts
    score_1 = score_domain_doc(Domain(is_active=True, _rev='12-xxx'), is_currently_chosen=True)
    score_2 = score_domain_doc(Domain(is_active=False, _rev='2-xxx'), is_currently_chosen=False)
    assert score_1 > score_2

    # If they're both active but one has rev_count 5, pick that one
    score_1 = score_domain_doc(Domain(is_active=True, _rev='1-xxx'), is_currently_chosen=True)
    score_2 = score_domain_doc(Domain(is_active=True, _rev='5-xxx'), is_currently_chosen=False)
    assert score_2 > score_1, (score_1, score_2)

    # But just 4 isn't enough to overcome "default advantage"
    score_1 = score_domain_doc(Domain(is_active=True, _rev='1-xxx'), is_currently_chosen=True)
    score_2 = score_domain_doc(Domain(is_active=True, _rev='4-xxx'), is_currently_chosen=False)
    assert score_1 > score_2, (score_1, score_2)
