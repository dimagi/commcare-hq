import csv
import logging
import os
from datetime import datetime, timezone

import attr
from dateutil.parser import parse as to_datetime

import django.db.models as models
from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Subscription
from corehq.apps.es.domains import DomainES, filters

from ...tinypanda import TinyPanda

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Categorize domains for forms and cases Couch to SQL migration"

    def add_arguments(self, parser):
        parser.add_argument('-o', '--output-dir', help="""
            Directory in which to store text files with categorized
            domains, one category per file, as well as summary file.
            Files are not written if not specified.
        """)

    def handle(self, output_dir=None, **options):
        main(output_dir)


def main(output_dir):
    data = TinyPanda(get_couch_domains())

    categories = {}
    domain_sets = []
    all_domains = len(data)
    total_domains = 0

    print("{:<15} {:>6} {:>12}  {}".format(
        "category",
        "domains",
        "submissions",
        "migration time",
    ))
    print("--")
    for name, query in [
        ("weird", get_weird),  # mistakes?

        ("no_forms", get_small(1)),

        ("fossilized", get_old(years=5)),
        ("inactive", get_old(years=1)),

        ("small", get_small(2000)),
        ("smallish", get_small(3500)),
        ("smallesque", get_small(5000)),

        ("super_large", get_large(720000)),
        ("large", get_large(60000)),

        ("moderate", lambda d: d),
    ]:
        subset = categories[name] = query(data)
        data -= subset

        if name == "weird":
            forms = time_to_complete = ""
        else:
            forms = subset['cp_n_forms'].apply(int).sum()
            time_to_complete = get_time_to_complete(forms)
        total_domains += len(subset)
        domain_sets.append((name, subset))

        print("{:<15} {:>6} {:>12}   {}".format(
            name,
            len(subset),
            f"{forms:,}" if forms else forms,
            time_to_complete,
        ))

        if output_dir is not None:
            path = os.path.join(output_dir, "%s.txt" % name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(subset['name']))

    assert total_domains == all_domains, (total_domains, all_domains)
    print("--")
    print("total {:>16}".format(total_domains))

    if output_dir is not None:
        print("writing domain.csv ...")
        write_domain_csv(output_dir, domain_sets)


def get_weird(data):
    return data[data.get("cp_n_active_cc_users") == None]  # noqa: E711


def get_small(upper_limit):
    def query(data):
        return data[data['cp_n_forms'].apply(int) < upper_limit]
    return query


def get_large(lower_limit):
    def query(data):
        return data[data['cp_n_forms'].apply(int) > lower_limit]
    return query


def get_old(*, years, limit=None, now=datetime.now(timezone.utc)):
    years_ago = now.replace(year=now.year - years)

    def query(data):
        where = data['cp_last_form'].apply(to_datetime) <= years_ago
        if limit is not None:
            where &= data['cp_n_forms'].apply(int) < limit
        return data[where]

    return query


def get_time_to_complete(forms):
    # Estimated migration throughput is about 24 forms/sec in the first
    # phase. Other phases add extra time. Estimate low here. And always
    # add more buffer time if/when sharing these numbers.
    num = forms / 10  # 10 forms/sec overall
    for divisor, name, next_div in [
        (60, "minutes", 60),
        (60, "hours", 24),
        (24, "days", 7),
        (7, "weeks", 4),
    ]:
        num = num / divisor
        if num < next_div * 2:
            break
    return "%.1f %s" % (num, name)


def get_couch_domains():
    """
    Returns a list of dicts of domain properties
    """
    return (
        DomainES()
        .filter(filters.OR(
            filters.term("use_sql_backend", False),
            filters.missing("use_sql_backend")
        ))
        .size(DOMAIN_COUNT_UPPER_BOUND)
        .sort("name")
        .values(
            "name",
            "cp_n_active_cc_users",
            "cp_n_forms",
            "cp_last_form",
        )
    )


DOMAIN_COUNT_UPPER_BOUND = 20000


def write_domain_csv(output_dir, domain_sets):
    path = os.path.join(output_dir, "domains.csv")
    with open(path, "w", encoding="utf-8") as fh:
        csvfile = csv.writer(fh)
        csvfile.writerow(Account.csv_headers)
        for name, domain_set in domain_sets:
            for acct in iter_accounts(domain_set, name):
                csvfile.writerow(acct.csv_row)


def iter_accounts(domain_set, category):
    subs = Subscription.visible_objects.filter(
        is_active=True,
        subscriber__domain__in=list(domain_set["name"]),
    ).annotate(
        domain_name=models.F("subscriber__domain"),
        plan_edition=models.F("plan_version__plan__edition"),
        is_enterprise=models.F("plan_version__plan__is_customer_software_plan"),
    ).values(
        "domain_name",
        "plan_edition",
        "is_enterprise",
    )
    subs = {s["domain_name"]: s for s in subs}
    for item in domain_set:
        name = item["name"]
        args = dict(item)
        args.pop("_id", None)
        if name in subs:
            args["plan_edition"] = subs[name]["plan_edition"]
            args["is_enterprise"] = subs[name]["is_enterprise"]
        yield Account(category=category, **args)


@attr.s
class Account:
    name = attr.ib()
    category = attr.ib()
    cp_n_active_cc_users = attr.ib(default=None)
    cp_n_forms = attr.ib(default=None)
    cp_last_form = attr.ib(default=None)
    plan_edition = attr.ib(default=None)
    is_enterprise = attr.ib(default=None)

    @property
    def time_to_complete(self):
        if self.cp_n_forms is None:
            return None
        return get_time_to_complete(self.cp_n_forms)

    csv_headers = [
        "Category",
        "Domain",
        "# forms",
        "Last submission",
        "Forms migration time",
        "Plan edition",
        "Enterprise",
    ]

    @property
    def csv_row(self):
        def get(prop):
            value = getattr(self, prop)
            return value if value is not None else ""
        return [get(prop) for prop in [
            "category",
            "name",
            "cp_n_forms",
            "cp_last_form",
            "time_to_complete",
            "plan_edition",
            "is_enterprise",
        ]]
