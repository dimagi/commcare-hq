from __future__ import absolute_import
from __future__ import unicode_literals
import itertools
import json
from collections import Counter

from couchdbkit import ResourceNotFound

from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider, ViewIDProvider, UserIDProvider, \
    SyncLogIDProvider, DomainKeyGenerator, DomainInListKeyGenerator
from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from corehq.feature_previews import all_previews
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import iter_docs

DOC_PROVIDERS = {
    DocTypeIDProvider(['Application']),
    DocTypeIDProvider(['CommtrackConfig']),
    DocTypeIDProvider(['DefaultConsumption']),
    ViewIDProvider('CommCareMultimedia', 'hqmedia/by_domain', DomainKeyGenerator()),
    DocTypeIDProvider(['MobileAuthKeyRecord']),
    DocTypeIDProvider(['Product']),
    DocTypeIDProvider(['Program']),
    DocTypeIDProvider(['CaseReminder']),
    DocTypeIDProvider(['CaseReminderHandler']),
    UserIDProvider(include_mobile_users=False),
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
    ViewIDProvider('Repeater', 'repeaters/repeaters', DomainInListKeyGenerator()),
    ViewIDProvider('RepeatRecord', 'repeaters/repeat_records', DomainInListKeyGenerator([None])),
    SyncLogIDProvider(),
}


# doc types that shouldn't have attachments dumped
ATTACHMENTS_BLACKLIST = [
    'SyncLog'
]


class CouchDataDumper(DataDumper):
    slug = 'couch'

    def dump(self, output_stream):
        stats = Counter()
        for doc_class, doc_ids in get_doc_ids_to_dump(self.domain):
            stats += self._dump_docs(doc_class, doc_ids, output_stream)
        return stats

    def _dump_docs(self, doc_class, doc_ids, output_stream):
        model_label = '{}.{}'.format(doc_class._meta.app_label, doc_class.__name__)
        count = 0
        couch_db = doc_class.get_db()
        for doc in iter_docs(couch_db, doc_ids, chunksize=500):
            count += 1
            doc = _get_doc_with_attachments(couch_db, doc)
            json.dump(doc, output_stream)
            output_stream.write('\n')
        self.stdout.write('Dumped {} {}\n'.format(count, model_label))
        return Counter({model_label: count})


def get_doc_ids_to_dump(domain):
    """
    :return: A generator of (doc_class, list(doc_ids))
    """
    for id_provider in DOC_PROVIDERS:
        for doc_type, doc_ids in id_provider.get_doc_ids(domain):
            yield doc_type, doc_ids


class ToggleDumper(DataDumper):
    slug = 'toggles'

    def dump(self, output_stream):
        count = 0
        for toggle in self._get_toggles_to_migrate():
            count += 1
            json.dump(toggle, output_stream)
            output_stream.write('\n')

        self.stdout.write('Dumped {} Toggles\n'.format(count))
        return Counter({'Toggle': count})

    def _get_toggles_to_migrate(self):
        from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
        from toggle.models import Toggle
        from toggle.shortcuts import namespaced_item

        all_user_ids = self._user_ids_in_domain()

        toggles_to_migrate = []
        domain_item = namespaced_item(self.domain, NAMESPACE_DOMAIN)

        for toggle in all_toggles() + all_previews():
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
        domain_obj = Domain.get_by_name(self.domain, strict=True)
        if not domain_obj:
            raise DomainDumpError("Domain not found: {}".format(self.domain))

        domain_dict = _get_doc_with_attachments(Domain.get_db(), domain_obj.to_json())
        domain_obj = Domain.wrap(domain_dict)
        json.dump(domain_obj.to_json(), output_stream)
        output_stream.write('\n')

        self.stdout.write('Dumping {} Domain\n'.format(1))
        return Counter({'Domain': 1})


def _get_doc_with_attachments(couch_db, doc):
    if doc.get('_attachments'):
        if doc['doc_type'] in ATTACHMENTS_BLACKLIST:
            del doc['_attachments']
        else:
            doc = couch_db.get(doc['_id'], attachments=True)
    return doc
