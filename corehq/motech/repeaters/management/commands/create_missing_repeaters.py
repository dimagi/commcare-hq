from uuid import UUID

from memoized import memoized
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.dbaccessors import domain_exists
from corehq.util.couchdb_management import couch_config

from ...models import Repeater, ConnectionSettings
from ...views.repeat_record_display import MISSING_VALUE


class Command(BaseCommand):
    help = """
    Migrate deleted repeaters from Couch to SQL.

    The new SQL repeaters are for repeat record display purposes
    only, and therefore have a minimal set of fields with meaningful
    values. Notably, they do not have related connection settings,
    and therefore may cause errors if referenced elsewhere. All new
    repeaters are created with a soft-deleted state.
    """

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, dry_run, **options):
        couch = couch_config.get_db("receiverwrapper")
        domain_by_repeater_id = dict(iter_missing_repeaters(couch))
        missing_repeaters = iter_docs(couch, list(domain_by_repeater_id))
        mode = " (dry run)" if dry_run else ""

        # recreate soft-deleted repeaters in SQL
        soft_migrated = []
        for docs in chunked(missing_repeaters, 100, list):
            for doc in docs:
                domain_name = domain_by_repeater_id[doc["_id"]]
                if domain_name != doc["domain"]:
                    print(f"Repeat record domain '{domain_name}' != "
                          f"'{doc['domain']}' of repeater {doc['_id']}")
            soft_migrated.extend(create_sql_repeaters(docs, dry_run))
        print_summary(soft_migrated, "soft", mode)

        # recreate hard-deleted repeaters in SQL
        soft_ids = {r.id for r in soft_migrated}
        remaining = [
            {"_id": x, "domain": d}
            for x, d in domain_by_repeater_id.items() if UUID(x) not in soft_ids
        ]
        hard_migrated = []
        for docs in chunked(remaining, 100, list):
            hard_migrated.extend(create_sql_repeaters(docs, dry_run))
        print()
        print_summary(hard_migrated, "hard", mode)


def print_summary(repeaters, category, mode):
    print(f"Migrated {len(repeaters)} {category}-deleted repeaters to SQL{mode}")
    for repeater in repeaters:
        print(f"  {repeater.domain} {repeater.id.hex} {repeater.name}")


def iter_missing_repeaters(couch):
    """Yield (id, domain) pairs of repeaters that do not exist in SQL"""
    @memoized
    def is_not_deleted(domain_name):
        return domain_exists(domain_name)

    couch_results = couch.view(
        'repeaters/repeat_records',
        startkey=[],
        endkey=[{}],
        reduce=True,
        group_level=2,
    ).all()
    sql_repeater_ids = set(Repeater.all_objects.order_by().values_list("id", flat=True))
    for result in couch_results:
        domain, repeater_id = result['key']
        if (
            repeater_id is not None  # view emits twice per record, skip the second
            and UUID(repeater_id) not in sql_repeater_ids
            and is_not_deleted(domain)
        ):
            yield repeater_id, domain


def create_sql_repeaters(docs, dry_run):
    objs = [make_deleted_sql_repeater(doc) for doc in docs]
    domains = {doc['domain'] for doc in docs}
    settings = {d: make_deleted_connection_settings(d) for d in domains}
    if not dry_run:
        ConnectionSettings.objects.bulk_create(settings.values())
        for obj in objs:
            assert settings[obj.domain].id is not None
            obj.connection_settings = settings[obj.domain]
        Repeater.objects.bulk_create(objs)
    return objs


def make_deleted_sql_repeater(doc):
    return Repeater(
        id=UUID(doc["_id"]),
        domain=doc["domain"],
        name=doc.get('name') or doc.get('url'),
        is_deleted=True,
    )


def make_deleted_connection_settings(domian):
    return ConnectionSettings(
        domain=domian,
        name=MISSING_VALUE,
        url="",
        is_deleted=True,
    )
