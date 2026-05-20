import csv
from pathlib import Path

import pytest

from calculate_keep import (
    _parse_linked_domains,
    main,
    COL_ENVIRONMENT,
    COL_REASON,
    COL_DOMAIN_NAME,
    COL_KEEP,
    COL_LINKED_DOMAIN_NAMES
)

HERE = Path(__file__).parent
OUTPUT_FILE = HERE / "case_search_usage_keep.csv"


@pytest.fixture(scope="module")
def output_rows():
    main()
    with open(OUTPUT_FILE, newline="") as f:
        rows = {
            (row[COL_ENVIRONMENT],row[COL_DOMAIN_NAME]): row
                for row in csv.DictReader(f)}
    return rows

def test_no_domain_kept_for_upstream_has_downstream(output_rows):
    '''
    There is a domain that is kept for 'has upstream keep' that has
    downstream domains that are not kept (for any reason)
    '''
    fail_rows = []
    for row in list(output_rows.values()):
        env = row[COL_ENVIRONMENT]
        linked_domains = _parse_linked_domains(row.get(COL_LINKED_DOMAIN_NAMES, ''), env)
        linked_domain_not_keep = [ld for ld in linked_domains if ld in output_rows and output_rows[ld][COL_KEEP] != 'TRUE']
        if row[COL_REASON] == 'has upstream keep' and any(linked_domain_not_keep):
            fail_rows += linked_domain_not_keep
            # fail_rows.append((env, row[COL_DOMAIN_NAME]))

    fail_str = '\n'.join([f'{env}, {domain}' for (env, domain) in fail_rows])
    assert not fail_rows, f'{len(fail_rows)} rows not kept with upstream that "has upstream keep" itself:\n{fail_str}'

def skip_test_linked_domain_exists(output_rows):
    fail_rows = []
    for row in list(output_rows.values()):
        env = row[COL_ENVIRONMENT]
        linked_domains = _parse_linked_domains(row.get(COL_LINKED_DOMAIN_NAMES, ''), env)
        for ld in linked_domains:
            if ld not in output_rows:
                fail_rows.append(ld)

    fail_str = '\n'.join([f'{env}, {domain}' for (env, domain) in fail_rows])
    assert not fail_rows, f'{len(fail_rows)} linked domains do not have FF:\n{fail_str}'


def test_no_domain_kept_for_downstream_has_upstream(output_rows):
    '''
    There is a domain that is kept for 'has downstream keep' that has an
    upstream domain that is not kept (for any reason)

    Or there is no domain that is not kept that has a downstream domain
    that is kept for 'has downstream keep'
    '''
    fail_rows = []
    for row in list(output_rows.values()):
        if row[COL_KEEP] != 'TRUE' and row[COL_LINKED_DOMAIN_NAMES]:
            env = row[COL_ENVIRONMENT]
            linked_domains = _parse_linked_domains(row.get(COL_LINKED_DOMAIN_NAMES, ''), env)
            linked_domains_with_has_downstream_keep = [
                ld
                for ld in linked_domains
                if ld in output_rows and output_rows[ld][COL_REASON] == 'has downstream keep']
            if linked_domains_with_has_downstream_keep:
                fail_rows += linked_domains_with_has_downstream_keep

    assert not fail_rows, f'{len(fail_rows)} rows with "has upstream keep" have downstream domains themselves'

SPOT_CHECKS = [
    ('www', 'co-carecoordination', 'TRUE', 'production domain'),
    ('www', 'co-carecoordination-dev', 'TRUE', 'has downstream keep'),
    ('www', 'co-carecoordination-uat', 'TRUE', 'has upstream keep'),
    ('www', 'casesearch', 'TRUE', 'qa domain'),
    ('www', 'mriese', 'FALSE', ''),
    ('staging', 'co-carecoordination-test', 'TRUE', 'has upstream keep'),
]

def test_spot_check(output_rows):
    if not SPOT_CHECKS:
        pytest.skip("no spot checks defined")
    for env, domain, expected_keep, reason in SPOT_CHECKS:
        row = output_rows[(env,domain)]
        assert row[COL_KEEP] == expected_keep, f'expected "{domain}" on "{env}" to be "{expected_keep}"'
        assert row[COL_REASON] == reason, f'expected "{domain}" on "{env}" to have reason "{reason}"'
