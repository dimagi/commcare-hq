"""Copy lookup tables referenced by applications imported within HQ."""

import re
from copy import deepcopy
from dataclasses import dataclass

from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception
from django.db import IntegrityError, transaction

from corehq.apps.fixtures.constants import LOOKUP_TABLE_TAG_MAX_LENGTH
from corehq.apps.fixtures.models import LookupTable, LookupTableRow
from corehq.apps.fixtures.upload.const import LOOKUP_TABLE_ROW_BATCH_SIZE

_ITEM_LIST_REFERENCE = re.compile(
    rf"item-list:(?P<tag>[\w.-]{{1,{LOOKUP_TABLE_TAG_MAX_LENGTH}}})(?![\w.-])"
)


@dataclass(frozen=True)
class LookupTableImportResult:
    tag_mapping: dict
    created_table_ids: tuple
    missing_tags: tuple
    failed_tags: tuple


def copy_lookup_tables(source_app_doc, source_domain, destination_domain):
    """Copy referenced tables and return information needed for rewriting and cleanup."""
    referenced_tags = _get_referenced_lookup_table_tags(source_app_doc)
    source_tables = {
        table.tag: table
        for table in LookupTable.objects.filter(domain=source_domain, tag__in=referenced_tags)
    }
    missing_tags = referenced_tags - source_tables.keys()
    tag_mapping = {}
    created_table_ids = []
    failed_tags = []
    for source_tag in sorted(source_tables):
        try:
            with transaction.atomic():
                copied_table = _copy_lookup_table(source_tables[source_tag], destination_domain)
        except Exception:
            notify_exception(
                None,
                message=(
                    f"Failed to copy lookup table '{source_tag}' "
                    f"from '{source_domain}' to '{destination_domain}'"
                ),
            )
            failed_tags.append(source_tag)
        else:
            tag_mapping[source_tag] = copied_table.tag
            created_table_ids.append(copied_table.id)

    return LookupTableImportResult(
        tag_mapping=tag_mapping,
        created_table_ids=tuple(created_table_ids),
        missing_tags=tuple(sorted(missing_tags)),
        failed_tags=tuple(failed_tags),
    )


def rewrite_lookup_table_references(app_doc, tag_mapping):
    """Update structured and string lookup-table references in ``app_doc`` in place."""
    _rewrite_fixture_type_fields(app_doc, tag_mapping)
    _rewrite_string_values(app_doc, tag_mapping)


def delete_copied_lookup_tables(destination_domain, table_ids):
    LookupTable.objects.filter(domain=destination_domain, id__in=table_ids).delete()


def _get_referenced_lookup_table_tags(value):
    tags = set()
    _collect_referenced_tags(value, tags)
    return tags


def _collect_referenced_tags(value, tags):
    if isinstance(value, dict):
        fixture_type = value.get("fixture_type")
        if isinstance(fixture_type, str):
            tags.add(fixture_type)
        for child in value.values():
            _collect_referenced_tags(child, tags)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_referenced_tags(child, tags)
    elif isinstance(value, str):
        tags.update(match.group("tag") for match in _ITEM_LIST_REFERENCE.finditer(value))


def _copy_lookup_table(source_table, destination_domain):
    copied_table = _create_lookup_table(source_table, destination_domain)
    source_rows = LookupTableRow.objects.filter(
        domain=source_table.domain,
        table=source_table,
    )

    for rows in chunked(source_rows.iterator(), LOOKUP_TABLE_ROW_BATCH_SIZE, list):
        LookupTableRow.objects.bulk_create([
            LookupTableRow(
                domain=destination_domain,
                table=copied_table,
                fields=deepcopy(row.fields),
                item_attributes=deepcopy(row.item_attributes),
                sort_key=row.sort_key,
            )
            for row in rows
        ])
    return copied_table


def _create_lookup_table(source_table, destination_domain):
    suffix = 0
    while True:
        destination_tag = _destination_tag(source_table.tag, suffix)
        try:
            with transaction.atomic():
                return LookupTable.objects.create(
                    domain=destination_domain,
                    tag=destination_tag,
                    fields=deepcopy(source_table.fields),
                    item_attributes=deepcopy(source_table.item_attributes),
                    description=source_table.description,
                    is_global=True,
                    is_synced=False,
                )
        except IntegrityError:
            if not LookupTable.objects.domain_tag_exists(destination_domain, destination_tag):
                raise
            suffix += 1


def _destination_tag(source_tag, suffix):
    if suffix == 0:
        return source_tag
    suffix_text = f"-{suffix}"
    return f"{source_tag[:LOOKUP_TABLE_TAG_MAX_LENGTH - len(suffix_text)]}{suffix_text}"


def _rewrite_fixture_type_fields(value, tag_mapping):
    if isinstance(value, dict):
        fixture_type = value.get("fixture_type")
        if fixture_type in tag_mapping:
            value["fixture_type"] = tag_mapping[fixture_type]
        for child in value.values():
            _rewrite_fixture_type_fields(child, tag_mapping)
    elif isinstance(value, list):
        for child in value:
            _rewrite_fixture_type_fields(child, tag_mapping)


def _rewrite_string_values(value, tag_mapping):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                value[key] = _rewrite_lookup_table_string(child, tag_mapping)
            else:
                _rewrite_string_values(child, tag_mapping)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                value[index] = _rewrite_lookup_table_string(child, tag_mapping)
            else:
                _rewrite_string_values(child, tag_mapping)


def _rewrite_lookup_table_string(value, tag_mapping):
    referenced_tags = {match.group("tag") for match in _ITEM_LIST_REFERENCE.finditer(value)}
    for source_tag in referenced_tags:
        destination_tag = tag_mapping.get(source_tag)
        if not destination_tag or destination_tag == source_tag:
            continue
        value = re.sub(
            rf"(?<![\w.-]){re.escape(source_tag)}_list/{re.escape(source_tag)}(?![\w.-])",
            f"{destination_tag}_list/{destination_tag}",
            value,
        )
        value = re.sub(
            rf"item-list:{re.escape(source_tag)}(?![\w.-])",
            f"item-list:{destination_tag}",
            value,
        )
    return value
