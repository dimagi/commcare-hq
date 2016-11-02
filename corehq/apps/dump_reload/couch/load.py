from collections import Counter

from corehq.apps.dump_reload.interface import DataLoader


class CouchDataLoader(DataLoader):
    def load_objects(self, object_strings):
        total_object_count = 0
        loaded_object_count = 0
        return total_object_count, Counter()
