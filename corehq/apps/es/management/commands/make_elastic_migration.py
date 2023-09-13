from argparse import ArgumentTypeError
from datetime import datetime

from django.core.management.base import CommandError
from django.db.migrations import Migration

from corehq.apps.es.migration_operations import (
    CreateIndex,
    DeleteIndex,
    UpdateIndexMapping,
)
from corehq.apps.es.transient_util import (
    iter_index_cnames,
    doc_adapter_from_cname,
)
from hqscripts.management.commands import makemigrations


class Command(makemigrations.Command):

    DJANGO_APP_LABEL = "es"

    help = "Creates a new migration for modifying Elasticsearch index(es)."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-c", "--create", metavar="CNAME[:NEW_INDEX_NAME]", dest="creates",
            default=[], type=self.adapter_and_name_type, action="append", help=(
                "Add a CreateIndex operation for index with canonical name "
                "CNAME. Use the optional ':NEW_INDEX_NAME' suffix to specify "
                "a name to use for the new index. The -c/--create option may "
                "be specified multiple times."
            ),
        )
        parser.add_argument(
            "-u", "--update", metavar="CNAME[:PROPERTY[,PROPERTY ...]]",
            dest="updates", default=[], type=self.adapter_and_properties_type,
            action="append", help=(
                "Add an UpdateIndexMapping operation for index with canonical "
                "name CNAME. Use the optional ':PROPERTY,...' suffix to "
                "specify which properties to update, omitting this suffix will "
                "update all properties. The -u/--update option may be "
                "specified multiple times."
            ),
        )
        parser.add_argument(
            "-d", "--delete", metavar="INDEX", dest="deletes", default=[],
            action="append", help=(
                "Add a DeleteIndex operation for the index with exact name "
                "%(metavar)s. The -d/--delete option may be specified multiple "
                "times."
            ),
        )
        parser.add_argument(
            "-t", "--target-versions", default=[], dest="target_versions", action="append",
            type=int, help=(
                "Target the elasticsearh versions for the mappings updates."
                "If not specified the mapping changes will be applied on all versions when migrations are run."
            ),
        )

    def handle(self, creates, updates, deletes, **options):
        # CLI argument values explicitly required by this custom handler
        self.empty = options["empty"]
        # self.migration_name is also required by 'write_migration_files()'
        self.migration_name = options["name"]

        self.target_versions = options['target_versions']

        # abort early if a migration name is provided but is invalid
        if self.migration_name and not self.migration_name.isidentifier():
            raise CommandError("The migration name must be a valid Python identifier.")

        # create the new migration object and its Elastic migration operations
        migration = self.build_migration(creates, updates, deletes)

        # perform makemigrations boilerplate to build the changes collection
        changes = self.arrange_migration_changes(migration)

        # CLI argument values that are only required for the super class(es)
        # 'write_migration_files()' method to work nominally.
        self.dry_run = options["dry_run"]
        self.verbosity = options["verbosity"]
        self.include_header = options["include_header"]
        self.lock_path = options["lock_path"]

        # write the new migration file
        self.write_migration_files(changes)

    def build_migration(self, creates, updates, deletes):
        """Returns a Migration instance with an operations list for each of the
        provided operation collections.

        :param creates: a list of ``(document_adapter, new_name)`` tuples
        :param updates: a list of ``(document_adapter, properties_dict)`` tuples
        :param deletes: a list of index names
        :returns: a Migration instance
        """
        migration = Migration("custom", self.DJANGO_APP_LABEL)
        if not self.empty:

            def verify_and_append_migration_operation(operation):
                """Ensure there are not multiple operations for the same index
                and append the operation to the migration."""
                default_op = ops_by_index_name.setdefault(operation.name, operation)
                if default_op is not operation:
                    raise CommandError("\n  - ".join([
                        f"Multiple operations for the same index ({operation.name}):",
                        repr(default_op),
                        repr(operation),
                    ]))
                migration.operations.append(operation)

            ops_by_index_name = {}
            # build 'create' operations
            for adapter, new_name in creates:
                verify_and_append_migration_operation(CreateIndex(
                    new_name,
                    adapter.type,
                    adapter.mapping,
                    adapter.analysis,
                    adapter.settings_key,
                    es_versions=self.target_versions,
                ))
            # build 'update' operations
            for adapter, properties in updates:
                verify_and_append_migration_operation(UpdateIndexMapping(
                    adapter.index_name,
                    adapter.type,
                    properties=properties,
                    es_versions=self.target_versions,
                ))
            # build 'delete' operations
            for index_name in deletes:
                verify_and_append_migration_operation(DeleteIndex(index_name, es_versions=self.target_versions))
        return migration

    def arrange_migration_changes(self, migration):
        """Performs the 'makemigrations' boilerplate responsible for building
        the 'changes' collection with the next migration number, auto migration
        name detection, etc.

        :param migration: a Migration instance
        :returns: changes dict
        """
        from django.apps import apps
        from django.db.migrations.autodetector import MigrationAutodetector
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
        from django.db.migrations.state import ProjectState

        loader = MigrationLoader(None)
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            NonInteractiveMigrationQuestioner(specified_apps=[migration.app_label]),
        )
        return autodetector.arrange_for_graph(
            changes={migration.app_label: [migration]},
            graph=loader.graph,
            migration_name=self.migration_name,
        )

    @staticmethod
    def adapter_type(value):
        """Returns a document adapter for the provided index canonical name
        supplied as the ``CNAME`` portion of the ``--create`` and ``--update``
        argument values.

        :param value: canonical name of the index.
        :raises: ``argparse.ArgumentTypeError`` if ``value`` is not a valid
            canonical name.
        """
        try:
            return doc_adapter_from_cname(value)
        except KeyError:
            raise ArgumentTypeError(
                f"Invalid index canonical name ({value}), "
                f"choices: {sorted(iter_index_cnames())}"
            )

    def adapter_and_name_type(self, value):
        """Returns a tuple of ``(document_adapter, new_index_name)`` for the
        provided ``--create`` argument value whose format is
        ``CNAME[:NEW_INDEX_NAME]`` where ``CNAME`` is a valid index canonical
        name and (optional) ``NEW_INDEX_NAME`` is the name to use for the new
        index.

        If the new name syntax (``:NEW_INDEX_NAME``) is omitted, an automatic
        new name is returned, derived from the index canonical name and today's
        date.

        :param value: the value of a ``--create`` argument
        :raises: ``argparse.ArgumentTypeError`` if ``value`` uses invalid syntax
            or refers to an invalid index canonical name or property name.
        """
        cname, delim, new_name = value.partition(":")
        adapter = self.adapter_type(cname)
        if not delim:
            new_name = f"{cname.replace('_', '-')}-{datetime.utcnow():%Y%m%d}"
        elif not new_name:
            raise ArgumentTypeError(
                f"Invalid (empty) new name for create action: {value!r}"
            )
        return adapter, new_name

    def adapter_and_properties_type(self, value):
        """Returns a tuple of ``(document_adapter, properties_dict)`` for the
        provided ``--update`` argument value whose format is
        ``CNAME[:PROPERTY[,PROPERTY ...]]`` where ``CNAME`` is a valid index
        canonical name and (optional) ``PROPERTY`` is/are valid property name(s)
        in the specified index's mapping.

        If the property list syntax (``:PROPERTY...``) is omitted, all
        properties for the index are returned.

        :param value: the value of an ``--update`` argument
        :raises: ``argparse.ArgumentTypeError`` if ``value`` uses invalid syntax
            or refers to an invalid index canonical name or property name.
        """
        cname, delim, property_names = value.partition(":")
        adapter = self.adapter_type(cname)
        properties = all_properties = adapter.mapping["properties"]
        if delim:
            properties = {}
            for name in property_names.split(","):
                if not name:
                    continue
                try:
                    properties[name] = all_properties[name]
                except KeyError:
                    raise ArgumentTypeError(
                        f"Invalid property name for index: {cname} (got "
                        f"{name!r}, expected one of {sorted(all_properties)})"
                    )
            if not properties:
                raise ArgumentTypeError(
                    f"Invalid (empty) property list for update action: {value!r}"
                )
        return adapter, properties
