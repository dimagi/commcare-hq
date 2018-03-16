from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


def perform_migration(domain, case_type, migration_xml):
    case_ids = CaseAccessors(domain).get_case_ids_in_domain(case_type)
    send_migration_to_formplayer(domain, case_ids, migration_xml)


def send_migration_to_formplayer(domain, case_ids, migration_xml):
    pass
