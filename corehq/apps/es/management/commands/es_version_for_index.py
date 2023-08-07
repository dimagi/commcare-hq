from django.core.management.base import BaseCommand
from corehq.apps.es.client import ElasticManageAdapter
from corehq.util.markup import SimpleTableWriter, TableRowFormatter


class Command(BaseCommand):
    help = ("Prints the ES version with which each index was created")

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-older-version-indexes',
            default=False,
            action='store_true',
            help="""Would only print indexes that were
            created with versions older than currently running ES""",
        )

    def _normalize_version(self, version):
        """
        Transforms es version string to human readable form
        """
        return f"{version[0]}.{version[2]}.{version[4]}"

    def handle(self, only_older_version_indexes, **options):
        es_manager = ElasticManageAdapter()
        indices = es_manager.get_indices()
        current_es_version = es_manager.info()['version']['number']

        rows = []
        for index_name, index_info in indices.items():
            version = self._normalize_version(index_info["settings"]["index"]["version"]["created"])
            aliases = list(index_info["aliases"].keys())
            alias = aliases[0] if aliases else "--"
            if only_older_version_indexes and current_es_version <= version:
                continue
            rows.append([index_name, alias, version])
        self.print_table(rows)

    def print_table(self, rows):
        row_formatter = TableRowFormatter(
            [60, 20, 20]
        )
        SimpleTableWriter(self.stdout, row_formatter).write_table(
            ['Index Name', 'Alias', 'ES Version'], rows=rows
        )
