from collections import Counter

from corehq.apps.dump_reload.interface import DataDumper


class CouchDataDumper(DataDumper):
    def dump(self, output_stream):
        return Counter()
