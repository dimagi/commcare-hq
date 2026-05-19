import csv
from pathlib import Path

import pytest

from calculate_keep import COL_ENVIRONMENT, COL_REASON, main, COL_DOMAIN_NAME, COL_KEEP

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


SPOT_CHECKS = [
    ('production', 'co-carecoordination', 'TRUE', 'production domain'),
    ('production', 'co-carecoordination-dev', 'TRUE', 'has downstream keep'),
    ('production', 'co-carecoordination-uat', 'TRUE', 'has upstream keep'),
    ('production', 'casesearch', 'TRUE', 'qa domain'),
    ('production', 'mriese', 'FALSE', ''),
    ('staging', 'co-carecoordination-test', 'TRUE', 'has upstream keep'),
]


def test_spot_check(output_rows):
    if not SPOT_CHECKS:
        pytest.skip("no spot checks defined")
    for env, domain, expected_keep, reason in SPOT_CHECKS:
        row = output_rows[(env,domain)]
        assert row[COL_KEEP] == expected_keep, f'expected "{domain}" on "{env}" to be "{expected_keep}"'
        assert row[COL_REASON] == reason, f'expected "{domain}" on "{env}" to have reason "{reason}"'
