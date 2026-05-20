"""
Calculate which domains to keep based on keep lists and usage data.
"""

# Add staging file ✅
# Read in all files ✅
# move to scripts directory ✅
# Integration test
#   - read and write files ✅
#   - spot check domains ✅
# Add reason column ✅
# fail on missing service type, plan name ✅
# handle service type, plan name being empty with not keep ✅


import csv
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent

COL_ENVIRONMENT = 'Environment'
COL_DOMAIN_NAME = 'Domain Name'
COL_SERVICE_TYPE = 'Service Type'
COL_PLAN_NAME = 'Plan Name'
COL_CASE_SEARCH_ENABLED = 'Case Search Enabled'
COL_LINKED_DOMAIN_NAMES = 'Linked Domain Names'
COL_KEEP = 'Keep'
COL_REASON = 'Reason'


def _load_csv(filename):
    with open(HERE / filename, newline="") as f:
        return list(csv.DictReader(f))


def _load_keep_set(filename):
    """Load a single-column CSV (first column) as a set of values."""
    with open(HERE / filename, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        return {row[0].strip() for row in reader if row}


def _load_keep_map(filename, key_col, value_col):
    """Load a two-column CSV as a dict mapping key_col -> bool."""
    with open(HERE / filename, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return {
            row[key_col].strip(): row[value_col].strip().upper() == "TRUE"
            for row in reader
        }


def _handle(usage_rows, keep_domains, plan_keep, service_keep):
    """
    Add keep-related columns to usage rows.

    :param usage_rows: list of dicts from case_search_usage_production.csv
    :param keep_domains: set of domain names to explicitly keep
    :param plan_keep: dict mapping plan name -> bool
    :param service_keep: dict mapping service type -> bool
    :returns: list of dicts with additional columns
    """
    result = []
    keep_outright = {}
    for row in usage_rows:
        row = dict(row)

        env = row[COL_ENVIRONMENT]
        domain_name = row[COL_DOMAIN_NAME]

        if domain_name in keep_domains:
            result.append({
                **row,
                COL_KEEP: 'TRUE',
                COL_REASON: 'qa domain'
            })
            keep_outright[env, domain_name] = True
            continue

        case_search_enabled = row.get(COL_CASE_SEARCH_ENABLED, "FALSE").strip().upper() == "TRUE"
        service_type = row.get(COL_SERVICE_TYPE, None)
        service_type_match = service_keep.get(service_type, None)
        if service_type != '' and service_type_match is None:
            raise ValueError(f'service type "{service_type}" is not mapped')
        plan_name = row.get(COL_PLAN_NAME, None)
        plan_name_match = plan_keep.get(plan_name, None)
        if plan_name != '' and plan_name_match is None:
            raise ValueError(f'plan name "{plan_name}" is not mapped')
        if case_search_enabled and service_type_match and plan_name_match:
            result.append({
                **row,
                COL_KEEP: 'TRUE',
                COL_REASON: 'production domain'
            })
            keep_outright[env, domain_name] = True
            continue

        result.append({
            **row,
            COL_KEEP: 'FALSE',
            COL_REASON: ''
        })

    for row in result:
        if row[COL_KEEP] != 'TRUE':
            env = row[COL_ENVIRONMENT]
            linked_domains = _parse_linked_domains(row.get(COL_LINKED_DOMAIN_NAMES, ''), env)
            keep_linked_domains = [keep_outright.get(env_ld, False) for env_ld in linked_domains]
            if any(keep_linked_domains):
                row[COL_KEEP] = 'TRUE'
                row[COL_REASON] = 'has downstream keep'

    keep_downstream_domains = set()

    for row in result:
        if row[COL_KEEP] == 'TRUE':
            env = row[COL_ENVIRONMENT]
            for env_ld in _parse_linked_domains(row.get(COL_LINKED_DOMAIN_NAMES, ''), env):
                keep_downstream_domains.add(env_ld)

    for row in result:
        if row[COL_KEEP] != 'TRUE':
            env = row[COL_ENVIRONMENT]
            domain_name = row[COL_DOMAIN_NAME]
            if (env, domain_name) in keep_downstream_domains:
                row[COL_KEEP] = 'TRUE'
                row[COL_REASON] = 'has upstream keep'

    return result

def _parse_linked_domains(linked_domains, default_env):
    domains_with_env = []
    if not linked_domains:
        return domains_with_env

    for linked_domain in linked_domains.split(','):
        result = urlparse(linked_domain)
        if result.netloc == '':
            domains_with_env.append((default_env, linked_domain))
        else:
            env = result.netloc.split('.')[0]
            domain_name = result.path.split('/')[2]
            domains_with_env.append((env, domain_name))


    return domains_with_env


def main():
    usage_rows = (
        _load_csv("case_search_usage_production.csv") +
        _load_csv("case_search_usage_eu.csv") +
        _load_csv("case_search_usage_india.csv") +
        _load_csv("case_search_usage_staging.csv")
    )
    keep_domains = _load_keep_set("keep_domains.csv")
    plan_keep = _load_keep_map("plan_name.csv", "plan name", "Keep")
    service_keep = _load_keep_map("service_type.csv", "serice type", "Keep")

    result = _handle(usage_rows, keep_domains, plan_keep, service_keep)

    if not result:
        print("No rows to write.")
        return

    out_path = HERE / "case_search_usage_keep.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result[0].keys())
        writer.writeheader()
        writer.writerows(result)

    print(f"Wrote {len(result)} rows to {out_path}")


if __name__ == "__main__":
    main()
