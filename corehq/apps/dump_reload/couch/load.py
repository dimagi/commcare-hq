from collections import Counter

from corehq.apps.dump_reload.interface import DataLoader


class CouchDataLoader(DataLoader):
    slug = 'couch'
    def load_objects(self, object_strings):
        total_object_count = 0
        for obj_string in object_strings:
            total_object_count += 1
        return total_object_count, Counter()
