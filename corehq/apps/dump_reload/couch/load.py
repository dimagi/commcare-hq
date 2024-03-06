import json
from collections import Counter

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.app_manager.models import Application, LinkedApplication, RemoteApp
from corehq.apps.dump_reload.exceptions import DataExistsException
from corehq.apps.dump_reload.interface import DataLoader
from corehq.util.couch import (
    IterDB,
    IterDBCallback,
    get_db_by_doc_type,
    get_document_class_by_doc_type,
)
from corehq.util.exceptions import DocumentClassNotFound


def drop_suffix(doc_type):
    if any(doc_type.endswith(suffix) for suffix in ('-Failed', '-Deleted')):
        doc_type, __ = doc_type.split('-')
    return doc_type


class CouchDataLoader(DataLoader):
    slug = 'couch'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dbs = {}
        self._success_counter = Counter()

    def load_objects(self, object_strings, force=False, dry_run=False):
        for obj_string in object_strings:
            doc = json.loads(obj_string)
            doc_type = drop_suffix(doc['doc_type'])
            if self._doc_type_matches_filter(doc_type):
                if dry_run:
                    self._success_counter[doc_type] += 1
                else:
                    db = self._get_db_for_doc_type(doc_type)
                    db.save(doc)

        for db in self._dbs.values():
            db.commit()

        return self._success_counter

    def _doc_type_matches_filter(self, doc_type):
        return not self.object_filter or self.object_filter.findall(doc_type)

    def _get_db_for_doc_type(self, doc_type):
        if doc_type not in self._dbs:
            couch_db = get_db_by_doc_type(doc_type)
            if couch_db is None:
                raise DocumentClassNotFound('No Document class with name "{}" could be found.'.format(doc_type))
            callback = LoaderCallback(self._success_counter, self.stdout)
            chunksize = 100
            if doc_type in [Application._doc_type, LinkedApplication._doc_type, RemoteApp._doc_type]:
                chunksize = 1
            db = IterDB(couch_db, new_edits=False, callback=callback, chunksize=chunksize)
            db.__enter__()
            self._dbs[doc_type] = db
        return self._dbs[doc_type]


class LoaderCallback(IterDBCallback):
    def __init__(self, _success_counter, stdout=None):
        self._success_counter = _success_counter
        self.stdout = stdout

    def post_commit(self, operation, committed_docs, success_ids, errors):
        if errors:
            raise Exception("Errors loading data", errors)

        success_doc_types = []
        for doc in committed_docs:
            doc_id = doc['_id']
            doc_type = drop_suffix(doc['doc_type'])
            doc_class = get_document_class_by_doc_type(doc_type)
            doc_label = '{}.{}'.format(doc_class._meta.app_label, doc_type)
            if doc_id in success_ids:
                success_doc_types.append(doc_label)

        self._success_counter.update(success_doc_types)

        if self.stdout:
            self.stdout.write('Loaded {} couch docs'.format(sum(self._success_counter.values())))


class ToggleLoader(DataLoader):
    slug = 'toggles'

    def load_objects(self, object_strings, force=False, dry_run=False):
        from corehq.toggles.models import Toggle
        count = 0
        for toggle_json in object_strings:
            if dry_run:
                count += 1
                continue

            toggle_dict = json.loads(toggle_json)
            slug = toggle_dict['slug']
            try:
                existing_toggle = Toggle.get(slug)
            except ResourceNotFound:
                Toggle.wrap(toggle_dict).save()
            else:
                existing_items = set(existing_toggle.enabled_users)
                items_to_load = set(toggle_dict['enabled_users'])
                enabled_for = existing_items | items_to_load
                existing_toggle.enabled_users = list(enabled_for)
                existing_toggle.save()

            count += 1

        self.stdout.write('Loaded {} Toggles'.format(count))
        return Counter({'Toggle': count})


class DomainLoader(DataLoader):
    slug = 'domain'

    def load_objects(self, object_strings, force=False, dry_run=False):
        from corehq.apps.domain.models import Domain
        objects = list(object_strings)
        assert len(objects) == 1, "Only 1 domain allowed per dump"

        domain_dict = json.loads(objects[0])

        domain_name = domain_dict['name']
        try:
            existing_domain = Domain.get_by_name(domain_name, strict=True)
        except ResourceNotFound:
            pass
        else:
            if existing_domain:
                if force:
                    self.stderr.write('Loading data for existing domain: {}'.format(domain_name))
                else:
                    raise DataExistsException("Domain: {}".format(domain_name))

        if not dry_run:
            Domain.get_db().bulk_save([domain_dict], new_edits=False)
        self.stdout.write('Loaded Domain')

        return Counter({'Domain': 1})
