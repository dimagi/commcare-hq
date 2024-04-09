import json
from collections import Counter

from couchdbkit import ResourceNotFound

from corehq.apps.dump_reload.couch.id_providers import (
    DocTypeIDProvider,
    DomainKeyGenerator,
    WebUserIDProvider,
    ViewIDProvider,
)
from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from corehq.apps.users.dbaccessors import get_all_usernames_by_domain
from corehq.feature_previews import all_previews
from dimagi.utils.couch.database import iter_docs

DOC_PROVIDERS = {
    DocTypeIDProvider('Application'),
    DocTypeIDProvider('LinkedApplication'),
    ViewIDProvider('CommCareMultimedia', 'hqmedia/by_domain', DomainKeyGenerator()),
    DocTypeIDProvider('MobileAuthKeyRecord'),
    DocTypeIDProvider('Product'),
    DocTypeIDProvider('Program'),
    WebUserIDProvider(),
    DocTypeIDProvider('CommCareUser'),
    DocTypeIDProvider('Group'),
    DocTypeIDProvider('ReportConfiguration'),
    DocTypeIDProvider('ReportNotification'),
    DocTypeIDProvider('ReportConfig'),
    DocTypeIDProvider('DataSourceConfiguration'),
    DocTypeIDProvider('FormExportInstance'),
    DocTypeIDProvider('FormExportDataSchema'),
    DocTypeIDProvider('ExportInstance'),
    DocTypeIDProvider('ExportDataSchema'),
    DocTypeIDProvider('CaseExportInstance'),
    DocTypeIDProvider('CaseExportDataSchema'),
}

DOC_PROVIDERS_BY_DOC_TYPE = {
    provider.doc_type: provider
    for provider in DOC_PROVIDERS
}


class CouchDataDumper(DataDumper):
    slug = 'couch'

    def dump(self, output_stream):
        stats = Counter()
        for doc_class, doc_ids in get_doc_ids_to_dump(self.domain, self.excludes, self.includes):
            stats += self._dump_docs(doc_class, doc_ids, output_stream)
        return stats

    def _dump_docs(self, doc_class, doc_ids, output_stream):
        model_label = '{}.{}'.format(doc_class._meta.app_label, doc_class.__name__)
        count = 0
        couch_db = doc_class.get_db()
        for doc in iter_docs(couch_db, doc_ids, chunksize=500):
            count += 1
            output_stream.write(json.dumps(doc))
            output_stream.write('\n')
        self.stdout.write('Dumped {} {}\n'.format(count, model_label))
        return Counter({model_label: count})


def get_doc_ids_to_dump(domain, exclude_doc_types=None, include_doc_types=None):
    """
    :return: A generator of (doc_class, list(doc_ids))
    """
    for id_provider in DOC_PROVIDERS:
        if include_doc_types and id_provider.doc_type not in include_doc_types:
            continue
        if exclude_doc_types and id_provider.doc_type in exclude_doc_types:
            continue

        for doc_type, doc_ids in id_provider.get_doc_ids(domain):
            yield doc_type, doc_ids


class ToggleDumper(DataDumper):
    slug = 'toggles'

    def dump(self, output_stream):
        count = 0
        for toggle in _get_toggles_to_migrate(self.domain):
            count += 1
            output_stream.write(json.dumps(toggle))
            output_stream.write('\n')

        self.stdout.write('Dumped {} Toggles\n'.format(count))
        return Counter({'Toggle': count})


def _get_toggles_to_migrate(domain):
    from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
    from corehq.toggles.models import Toggle
    from corehq.toggles.shortcuts import namespaced_item

    domain_item = namespaced_item(domain, NAMESPACE_DOMAIN)
    usernames = set(get_all_usernames_by_domain(domain))

    for toggle in all_toggles() + all_previews():
        try:
            current_toggle = Toggle.get(toggle.slug)
        except ResourceNotFound:
            continue

        enabled_for = set(current_toggle.enabled_users)

        new_toggle = Toggle(slug=toggle.slug, enabled_users=[])
        if domain_item in enabled_for:
            new_toggle.enabled_users.append(domain_item)

        enabled_users = enabled_for & usernames
        new_toggle.enabled_users.extend(list(enabled_users))

        if new_toggle.enabled_users:
            yield new_toggle.to_json()


class DomainDumper(DataDumper):
    slug = 'domain'

    def dump(self, output_stream):
        from corehq.apps.domain.models import Domain
        domain_obj = Domain.get_by_name(self.domain, strict=True)
        if not domain_obj:
            raise DomainDumpError("Domain not found: {}".format(self.domain))

        json.dump(domain_obj.to_json(), output_stream)
        output_stream.write('\n')

        self.stdout.write('Dumping {} Domain\n'.format(1))
        return Counter({'Domain': 1})
