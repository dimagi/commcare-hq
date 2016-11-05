import json
from collections import Counter

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.dump_reload.exceptions import DataExistsException
from corehq.apps.dump_reload.interface import DataLoader
from corehq.util.couch import IterDB, get_db_by_doc_type, IterDBCallback, get_document_class_by_doc_type


class CouchDataLoader(DataLoader):
    slug = 'couch'

    def __init__(self, stdout=None, stderr=None):
        super(CouchDataLoader, self).__init__(stdout, stderr)
        self._dbs = {}
        self.success_counter = Counter()

    def _get_db_for_doc_type(self, doc_type):
        if doc_type not in self._dbs:
            db = IterDB(get_db_by_doc_type(doc_type), new_edits=False, callback=LoaderCallback(self.success_counter))
            db.__enter__()
            self._dbs[doc_type] = db
        return self._dbs[doc_type]

    def load_objects(self, object_strings, force=False):
        total_object_count = 0
        for obj_string in object_strings:
            total_object_count += 1
            doc = json.loads(obj_string)
            db = self._get_db_for_doc_type(doc['doc_type'])
            db.save(doc)

        for db in self._dbs.values():
            db.commit()

        return total_object_count, self.success_counter


class LoaderCallback(IterDBCallback):
    def __init__(self, success_counter):
        self.success_counter = success_counter

    def post_commit(self, operation, committed_docs, success_ids, errors):
        if errors:
            raise Exception("Errors loading data", errors)

        success_doc_types = []
        for doc in committed_docs:
            doc_id = doc['_id']
            doc_type = doc['doc_type']
            doc_class = get_document_class_by_doc_type(doc_type)
            doc_label = '(couch) {}.{}'.format(doc_class._meta.app_label, doc_type)
            if doc_id in success_ids:
                success_doc_types.append(doc_label)

        self.success_counter.update(success_doc_types)


class ToggleLoader(DataLoader):
    slug = 'toggles'

    def load_objects(self, object_strings, force=False):
        from toggle.models import Toggle
        count = 0
        for toggle_json in object_strings:
            toggle_dict = json.loads(toggle_json)
            slug = toggle_dict['slug']
            try:
                existing_toggle = Toggle.get(slug)
            except ResourceNotFound:
                Toggle.wrap(toggle_dict).save()
            else:
                enabled_for = set(existing_toggle.enabled_users) | set(toggle_dict['enabled_users'])
                existing_toggle.enabled_users = list(enabled_for)
                existing_toggle.save()

            count += 1
        return count, Counter({'Toggle': count})


class DomainLoader(DataLoader):
    slug = 'domain'

    def load_objects(self, object_strings, force=False):
        from corehq.apps.domain.models import Domain
        objects = list(object_strings)
        assert len(objects) == 1, "Only 1 domain allowed per dump"

        domain_dict = json.loads(objects[0])

        domain_name = domain_dict['name']
        try:
            Domain.get_by_name(domain_name)
        except ResourceNotFound:
            pass
        else:
            if force:
                self.stderr.write('Loading data for existing domain: {}'.format(domain_name))
            else:
                raise DataExistsException("Domain: {}".format(domain_name))

        Domain.get_db().bulk_save([domain_dict], new_edits=False)

        return 1, Counter({'Domain': 1})
