"""
Usage, in ``./manage.py shell``: paste this file, then

    check_domain()                         # domain can forward now, Connect repeater found
    forms = find_missing_forms()
    report(forms)                          # read-only
    register_missing_forms(forms)          # dry run: rechecks, registers nothing
    register_missing_forms(forms, dry_run=False)   # actually register + forward, throttled

Forms are registered oldest first so Connect receives them in submission order.
If the shell drops partway through, run ``find_missing_forms()`` again: forms
already registered now have a repeat record, so only the rest are returned,
plus any the repeater filters out (listed by ``register_missing_forms()``).
"""
import time
from collections import Counter
from datetime import datetime, timezone

from django.db.models import Q

from corehq.form_processor.models import XFormInstance
from corehq.motech.repeaters.models import (
    FormRepeater,
    Repeater,
    RepeatRecord,
    domain_can_forward_now,
)
from corehq.sql_db.util import paginate_query_across_partitioned_databases

DOMAIN = "ccc-chc-eha-c-2024-25"
# Paused on 2026-09-01. Pad by a day; forms that already have a repeat record
# are skipped, so starting early is harmless.
RECEIVED_FROM = datetime(2026, 8, 31, tzinfo=timezone.utc)
CONNECT_HOST = "connect.dimagi.com"


def get_connect_repeaters(domain=DOMAIN):
    """
    Form repeaters in ``domain`` that forward to Connect. Matched by URL,
    not type, because some domains use a plain "Forward Forms" repeater
    rather than a ConnectFormRepeater.
    """
    return [
        repeater for repeater in Repeater.objects.by_domain(domain)
        if isinstance(repeater, FormRepeater)
        and CONNECT_HOST in repeater.connection_settings.url
    ]


def check_domain(domain=DOMAIN):
    ok = True
    if not domain_can_forward_now(domain):
        print(f"{domain} cannot forward now: still paused, or PAUSE_DATA_FORWARDING is on.")
        ok = False
    repeaters = get_connect_repeaters(domain)
    if not repeaters:
        print(f"{domain} has no form repeater forwarding to {CONNECT_HOST}.")
        ok = False
    for repeater in repeaters:
        print(f"Repeater {repeater.id} name={repeater.name!r} is_paused={repeater.is_paused} "
              f"url={repeater.connection_settings.url}")
        if repeater.is_paused:
            ok = False
    print("OK" if ok else "NOT OK: fix the above before registering")
    return ok


def _iter_forms_received_since(domain, received_from):
    q_expr = (
        Q(domain=domain)
        & Q(state=XFormInstance.NORMAL)
        & Q(received_on__gte=received_from.replace(tzinfo=None))
    )
    yield from paginate_query_across_partitioned_databases(
        XFormInstance,
        q_expr,
        values=["form_id", "received_on", "app_id"],
        load_source="ci_1040_connect_resync",
    )


def _forwarded_form_ids(form_ids, repeater_ids, domain, chunk_size=1000):
    """
    The subset of ``form_ids`` that already have a repeat record for one of
    ``repeater_ids``. Looks up by ``payload_id`` so Postgres uses that index,
    instead of reading every repeat record the domain has.
    """
    forwarded = set()
    for start in range(0, len(form_ids), chunk_size):
        forwarded.update(
            RepeatRecord.objects.filter(
                payload_id__in=form_ids[start:start + chunk_size],
                domain=domain,
                repeater_id__in=repeater_ids,
            ).values_list("payload_id", flat=True)
        )
    return forwarded


def find_missing_forms(domain=DOMAIN, received_from=RECEIVED_FROM):
    """
    Returns forms received since ``received_from`` that have no Connect
    repeat record, oldest first, as dicts with ``id``, ``received_on``
    and ``app_id``.
    """
    repeater_ids = [r.id for r in get_connect_repeaters(domain)]
    started = time.monotonic()
    forms = list(_iter_forms_received_since(domain, received_from))
    forwarded = _forwarded_form_ids([form_id for form_id, _, _ in forms], repeater_ids, domain)
    missing = sorted(
        (
            {"id": form_id, "received_on": received_on, "app_id": app_id}
            for form_id, received_on, app_id in forms
            if form_id not in forwarded
        ),
        key=lambda f: f["received_on"],
    )
    print(f"Queries took {time.monotonic() - started:.1f}s: {len(forms)} forms since "
          f"{received_from}, {len(missing)} with no Connect repeat record")
    return missing


def report(forms):
    print(f"Forms with no Connect repeat record: {len(forms)}")
    if not forms:
        return
    print(f"Earliest received_on: {forms[0]['received_on']}")
    print(f"Latest received_on:   {forms[-1]['received_on']}")
    print("\nBy app:")
    for app_id, n in Counter(f["app_id"] for f in forms).most_common():
        print(f"  {app_id}: {n}")
    print("\nBy day received:")
    for day, n in sorted(Counter(f["received_on"].date() for f in forms).items()):
        print(f"  {day}: {n}")


def register_missing_forms(forms, dry_run=True, batch_size=100, pause_seconds=30,
                           domain=DOMAIN):
    """
    Register a Connect repeat record for each form in ``forms``,
    ``batch_size`` at a time with ``pause_seconds`` between batches so
    Connect isn't hit with the whole backlog at once. Each batch is
    rechecked for existing repeat records, so rerunning after an
    interruption won't create duplicates.

    Forms the repeater's own filters reject (device logs, xmlns allowlist,
    user blocklist) are counted as ``filtered`` rather than registered.
    They never get a repeat record, so ``find_missing_forms()`` keeps
    returning them; after a full run it should return only these.
    """
    if not dry_run and not check_domain(domain):
        return
    repeaters = get_connect_repeaters(domain)
    repeater_ids = [r.id for r in repeaters]
    form_ids = [f["id"] for f in forms]
    total = len(form_ids)
    print(f"{'[dry run] ' if dry_run else ''}{total} forms to check")
    registered = skipped = 0
    filtered = []
    for start in range(0, total, batch_size):
        batch = form_ids[start:start + batch_size]
        already = _forwarded_form_ids(batch, repeater_ids, domain)
        todo = [form_id for form_id in batch if form_id not in already]
        skipped += len(batch) - len(todo)
        for form in XFormInstance.objects.get_forms(todo, ordered=True):
            allowed = [r for r in repeaters if r.allowed_to_forward(form)]
            if not allowed:
                filtered.append(form.form_id)
                continue
            if not dry_run:
                for repeater in allowed:
                    repeater.register(form)
            registered += 1
        print(f"  {start + len(batch)}/{total} checked, {registered} "
              f"{'would be ' if dry_run else ''}registered, {skipped} skipped, "
              f"{len(filtered)} filtered by repeater")
        if not dry_run and start + batch_size < total:
            time.sleep(pause_seconds)
    if filtered:
        print(f"Filtered by repeater (not forwarded): {filtered}")
    if dry_run:
        print("Call register_missing_forms(forms, dry_run=False) to register.")
    return registered
