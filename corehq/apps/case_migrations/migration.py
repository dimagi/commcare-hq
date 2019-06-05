from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor, iter_all_ids_chunked


def perform_migration(domain, case_type, migration_xml):
    accessor = CaseReindexAccessor(domain=domain, case_type=case_type)
    for case_ids in iter_all_ids_chunked(accessor):
        send_migration_to_formplayer(domain, case_ids, migration_xml)


def send_migration_to_formplayer(domain, case_ids, migration_xml):
    pass
