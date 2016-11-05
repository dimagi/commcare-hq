import itertools
import json
from collections import Counter

from couchdbkit import ResourceNotFound

from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider, ViewIDProvider
from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from dimagi.utils.couch.database import iter_docs

DOC_PROVIDERS = {
    DocTypeIDProvider(['Location']),
    DocTypeIDProvider(['Application']),
    DocTypeIDProvider(['CommtrackConfig']),
    DocTypeIDProvider(['DefaultConsumption']),
    ViewIDProvider('CommCareMultimedia', 'hqmedia/by_domain'),
    DocTypeIDProvider(['MobileAuthKeyRecord']),
    DocTypeIDProvider(['Product']),
    DocTypeIDProvider(['Program']),
    DocTypeIDProvider(['CaseReminder']),
    DocTypeIDProvider(['CaseReminderHandler']),
    DocTypeIDProvider(['WebUser']),
    DocTypeIDProvider(['CommCareUser']),
    DocTypeIDProvider(['UserRole']),
    DocTypeIDProvider(['Group']),
    DocTypeIDProvider(['ReportConfiguration']),
    DocTypeIDProvider(['ReportNotification']),
    DocTypeIDProvider(['ReportConfig']),
    DocTypeIDProvider(['DataSourceConfiguration']),
    DocTypeIDProvider(['FormExportInstance']),
    DocTypeIDProvider(['FormExportDataSchema']),
    DocTypeIDProvider(['ExportInstance']),
    DocTypeIDProvider(['ExportDataSchema']),
    DocTypeIDProvider(['CaseExportInstance']),
    DocTypeIDProvider(['CaseExportDataSchema']),
    DocTypeIDProvider(['CustomDataFieldsDefinition']),
    DocTypeIDProvider(['FixtureOwnership']),
    DocTypeIDProvider(['FixtureDataType']),
    DocTypeIDProvider(['FixtureDataItem']),
    # 'SimplifiedSyncLog'
    # 'SyncLog' ? don't think new domains use this at all
    # 'AdminUserRole' ? don't think this is a doc type that gets saved to the DB
}


class CouchDataDumper(DataDumper):
    slug = 'couch'

    def dump(self, output_stream):
        stats = Counter()
        for doc_class, doc_ids in get_doc_ids_to_dump(self.domain):
            stats += _dump_docs(doc_class, doc_ids, output_stream)
        return stats


def _dump_docs(doc_class, doc_ids, output_stream):
    model_label = '{}.{}'.format(doc_class._meta.app_label, doc_class.__name__)
    count = 0
    for doc in iter_docs(doc_class.get_db(), doc_ids):
        count += 1
        json.dump(doc, output_stream)
        output_stream.write('\n')
    return Counter({model_label: count})


def get_doc_ids_to_dump(domain):
    """
    :return: A generator of (doc_class, list(doc_ids))
    """
    for id_provider in DOC_PROVIDERS:
        yield itertools.chain(*id_provider.get_doc_ids(domain))


class ToggleDumper(DataDumper):
    slug = 'toggles'

    def dump(self, output_stream):
        count = 0
        for toggle in self._get_toggles_to_migrate():
            count += 1
            json.dump(toggle, output_stream)
            output_stream.write('\n')
        return Counter({'Toggle': count})

    def _get_toggles_to_migrate(self):
        from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
        from toggle.models import Toggle
        from toggle.shortcuts import namespaced_item

        all_user_ids = self._user_ids_in_domain()

        toggles_to_migrate = []
        domain_item = namespaced_item(self.domain, NAMESPACE_DOMAIN)

        for toggle in all_toggles():
            try:
                current_toggle = Toggle.get(toggle.slug)
            except ResourceNotFound:
                continue

            enabled_for = set(current_toggle.enabled_users)

            new_toggle = Toggle(slug=toggle.slug, enabled_users=[])
            if domain_item in enabled_for:
                new_toggle.enabled_users.append(domain_item)

            enabled_users = enabled_for & all_user_ids
            new_toggle.enabled_users.extend(list(enabled_users))

            if new_toggle.enabled_users:
                toggles_to_migrate.append(new_toggle.to_json())

        return toggles_to_migrate

    def _user_ids_in_domain(self):
        from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
        user_ids = set()
        for doc_type in ('CommCareUser', 'WebUser'):
            user_ids.update(set(get_doc_ids_in_domain_by_type(self.domain, doc_type)))
        return user_ids


class DomainDumper(DataDumper):
    slug = 'domain'

    def dump(self, output_stream):
        from corehq.apps.domain.models import Domain
        domain_obj = Domain.get_by_name(self.domain)
        if not domain_obj:
            raise DomainDumpError("Domain not found: {}".format(self.domain))

        json.dump(domain_obj.to_json(), output_stream)
        output_stream.write('\n')

        return Counter({'Domain': 1})
