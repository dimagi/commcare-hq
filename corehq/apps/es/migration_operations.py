import logging
import sys
from datetime import datetime
from difflib import unified_diff
from tempfile import NamedTemporaryFile

from django.core.management import call_command
from django.core.management.base import CommandError, OutputWrapper
from django.core.management.color import color_style
from django.db.migrations import RunPython

from corehq.apps.es.index.settings import render_index_tuning_settings

log = logging.getLogger(__name__)


class BaseElasticOperation(RunPython):
    """Perform an operation for an Elasticsearch index."""

    def run(self, *args, **kw):
        raise NotImplementedError(type(self).__name__)

    def reverse_run(self, *args, **kw):
        raise NotImplementedError(type(self).__name__)

    def _should_skip_operation(self, mapping_es_major_versions):
        """
        The mappings should be applied on ES if running version of ES is same as the targetted es versions.
        :param mapping_es_major_version: an list consisting of all major versions that the mapping support
        """
        from corehq.apps.es.client import manager
        current_es_major_version = manager.elastic_major_version
        if current_es_major_version in mapping_es_major_versions:
            return False
        log.info(f"The mappings were created for Elasticsearch version/s {mapping_es_major_versions}")
        log.info(f"Current Elasticsearch version in {current_es_major_version}. Skipping the operation.")
        return True

    def __repr__(self):
        return f"<{type(self).__name__} index={self.name!r}>"


class CreateIndex(BaseElasticOperation):
    """Create an Elasticsearch index."""

    serialization_expand_args = ["mapping", "analysis"]

    def __init__(self, name, type_, mapping, analysis, settings_key, comment=None, es_versions=[]):
        """CreateIndex operation.

        :param name: the name of the index to be created.
        :param type_: the index ``_type`` for the mapping.
        :param mapping: the mapping to apply to the new index.
        :param analysis: the analysis configuration to apply to the new index
        :param settings_key: the index settings key to use for rendering
            tuning settings.
        :param comment: Optional value to set on the index's
            ``mapping._meta.comment`` property.
        :param es_versions: Optional (default []) list of supported ES versions.
            If specified, the mappings will only be applied on those ES versions.
        """
        super().__init__(self.run, self.reverse_run)
        self.name = name
        self.type = type_
        self.mapping = mapping
        self.analysis = analysis
        self.settings_key = settings_key
        self.comment = comment
        self.es_versions = es_versions

    def deconstruct(self):
        kwargs = {}
        if self.comment is not None:
            kwargs["comment"] = self.comment
        kwargs['es_versions'] = self.es_versions
        mapping = {k: v for k, v in self.mapping.items() if k != "_meta"}
        return (
            self.__class__.__qualname__,
            [self.name, self.type, mapping, self.analysis, self.settings_key],
            kwargs,
        )

    def run(self, *args, **kw):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            # skip running the operation if compatible ES versions are provided
            # and mapping is created for a differnt es version
            return

        from corehq.apps.es.client import manager
        log.info("Creating Elasticsearch index: %s" % self.name)
        manager.index_create(self.name, self.render_index_metadata(
            self.type,
            self.mapping,
            self.analysis,
            self.settings_key,
            self.comment,
        ))
        manager.index_configure_for_standard_ops(self.name)

    def reverse_run(self, *args, **kw):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            return
        DeleteIndex(self.name).run(*args, **kw)

    def describe(self):
        return f"Create Elasticsearch index {self.name!r}"

    @staticmethod
    def render_index_metadata(type_, mapping, analysis, settings_key, comment):
        # NOTE: mapping might be JsonObject.DictProperty, handle with care:
        #       Do not make copies of JsonObject properties, those objects have
        #       some nasty bugs that will bite in really obscure ways.
        #       For example:
        # >>> from copy import copy
        # >>> from corehq.pillows.mappings import GROUP_INDEX_INFO as index_info
        # >>> list(index_info.meta)
        # ['settings']
        # >>> list(index_info.to_json()['meta'])
        # ['settings']
        # >>> meta = copy(index_info.meta)
        # >>> meta.update({'mappings': None})
        # >>> list(index_info.meta)
        # ['settings']
        # >>> list(index_info.to_json()['meta'])
        # ['settings', 'mappings']
        mapping = dict(mapping)
        mapping["_meta"] = dict(mapping.pop("_meta", {}))
        mapping["_meta"].update(make_mapping_meta(comment))
        settings = {"analysis": analysis}
        settings.update(render_index_tuning_settings(settings_key))
        return {
            "mappings": {type_: mapping},
            "settings": settings,
        }


class DeleteIndex(BaseElasticOperation):
    """Delete an Elasticsearch index."""

    serialization_expand_args = ["reverse_params"]

    def __init__(self, name, reverse_params=None, es_versions=[]):
        """DeleteIndex operation.

        :param name: the name of the index to be deleted.
        :param reverse_params: an iterable of four items containing ``(type,
            mapping, analysis, settings_key)`` for reversing the migration. If
            ``None`` (the default), the operation is irreversible.
        :param es_versions: Optional (default []) list of supported ES versions.
            If specified, the mappings will only be applied on those ES versions.
        """
        super().__init__(self.run, self.reverse_run if reverse_params else None)
        self.name = name
        self.es_versions = es_versions
        if reverse_params:
            type_, mapping, analysis, settings_key = reverse_params
            self.reverse_type = type_
            self.reverse_mapping = mapping
            self.reverse_analysis = analysis
            self.reverse_settings_key = settings_key

    def deconstruct(self):
        kwargs = {}
        kwargs['es_versions'] = self.es_versions
        if self.reversible:
            kwargs["reverse_params"] = (
                self.reverse_type,
                self.reverse_mapping,
                self.reverse_analysis,
                self.reverse_settings_key,
            )
        return (
            self.__class__.__qualname__,
            [self.name],
            kwargs,
        )

    def run(self, *args, **kw):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            return
        from corehq.apps.es.client import manager
        log.info("Deleting Elasticsearch index: %s" % self.name)
        manager.index_delete(self.name)

    def reverse_run(self, *args, **kw):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            return
        create_kw = {
            "name": self.name,
            "type_": self.reverse_type,
            "mapping": self.reverse_mapping,
            "analysis": self.reverse_analysis,
            "settings_key": self.reverse_settings_key,
            "comment": f"Reversal of {self}",
        }
        CreateIndex(**create_kw).run(*args, **kw)

    def describe(self):
        return f"Delete Elasticsearch index {self.name!r}"


class UpdateIndexMapping(BaseElasticOperation):
    """Update the mapping for an Elasticsearch index.

    This operation will apply mapping changes to an existing index as follows:

    1. The existing index mapping is fetched in order to acquire a known "safe
       to apply" mapping payload, hereinafter referred to as "the payload".
    2. The ``properties`` item in the payload is replaced with properties from
       the migration operation (i.e. ``self.properties``).
    3. The ``_meta`` item in the payload is updated by setting/replacing the
       ``created`` value (always), and the ``comment`` value (maybe, depending
       on whether or not a comment is provided).
    4. The payload is then applied to the existing index via the "Put Mapping"
       API.

    Note that this migration operation does not currently support changing
    mapping values outside of the ``_meta`` and ``properties`` items (e.g.
    ``date_detection``, ``dynamic``, etc). This functionality remains as a task
    for the future.

    See the :ref:`updating-elastic-index-mappings` documentation for further
    details.

    See also the `Put Mapping`_ Elastic documentation for API details.

    .. _Put Mapping: https://www.elastic.co/guide/en/elasticsearch/reference/2.4/indices-put-mapping.html
    """

    serialization_expand_args = ["properties"]

    def __init__(self, name, type_, properties, comment=None, print_diff=True, es_versions=[]):
        """UpdateIndexMapping operation.

        :param name: the name of the index.
        :param type_: the index ``_type`` for the mapping.
        :param properties: the ``properties`` portion of an index mapping to
            apply to the index.
        :param comment: Optional value to set on the index's
            ``mapping._meta.comment`` property. If ``None`` (the default), then
            the existing ``mapping._meta.comment`` value (if one exists) is
            retained.
        :param print_diff: Optional (default ``True``) set to ``False`` to
            disable printing the mapping diff.
        :param es_versions: Optional (default []) list of supported ES versions.
            If specified, the mappings will only be applied on those ES versions.
        """
        super().__init__(self.run)
        self.name = name
        self.type = type_
        self.properties = properties
        self.comment = comment
        self.print_diff = print_diff
        self.stream = sys.stdout  # stream where the diff is printed
        self.es_versions = es_versions

    def deconstruct(self):
        kwargs = {}
        if self.comment is not None:
            kwargs["comment"] = self.comment
        if not self.print_diff:
            kwargs["print_diff"] = False
        kwargs['es_versions'] = self.es_versions
        return (
            self.__class__.__qualname__,
            [self.name, self.type, self.properties],
            kwargs,
        )

    def run(self, *args, **kw):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            return
        from corehq.apps.es.client import manager
        mapping = manager.index_get_mapping(self.name, self.type) or {}
        mapping.setdefault("_meta", {}).update(make_mapping_meta(self.comment))
        mapping["properties"] = self.properties
        log.info("Updating mappings for Elasticsearch index: %s" % self.name)
        if self.print_diff:
            before = self.get_mapping_text_lines()
        response = manager.index_put_mapping(self.name, self.type, mapping)
        if not response.get("acknowledged", False):
            # Added because this condition is checked in historic put mapping
            # logic, but it is not clear why/when this happens.
            raise MappingUpdateFailed(f"Mapping update failed for index: {self.name}")
        if self.print_diff:
            self.show_diff(before, self.get_mapping_text_lines())

    def get_mapping_text_lines(self):
        """Fetch the existing mapping for the index as printable text."""
        index_ident = f"{self.name}:{self.type}"
        with NamedTemporaryFile("w+") as file:
            argv = ["print_elastic_mappings", "--no-names", "-o", file.name, index_ident]
            try:
                call_command(*argv)
            except CommandError as exc:
                log.warning(f"failed to fetch mapping for index {self.name!r} ({exc!s})")
                return []
            file.seek(0)
            return list(file)

    def show_diff(self, before, after):
        """Print a mapping diff."""
        if getattr(self.stream, "isatty", lambda: False)():
            style = color_style()
            addition = style.SUCCESS  # green
            deletion = style.ERROR  # red
        else:
            addition = deletion = None
        stream_wrapper = OutputWrapper(self.stream)
        for line in unified_diff(before, after, "before.py", "after.py"):
            if line.startswith("-") and not line.startswith("--- "):
                style_func = deletion
            elif line.startswith("+") and not line.startswith("+++ "):
                style_func = addition
            else:
                style_func = None
            stream_wrapper.write(line, style_func, ending="")

    def describe(self):
        return f"Update the mapping for Elasticsearch index {self.name!r}"


def make_mapping_meta(comment=None):
    """Return a dict containing the common ``mapping._meta`` values to use when
    writing (creating or updating) an Elastic index mapping.

    :param comment: optionally include this comment in the return value. If
        ``None`` (the default) a ``comment`` key will not be included in the
        return value
    """
    meta = {"created": datetime.isoformat(datetime.utcnow())}
    if comment is not None:
        meta["comment"] = comment
    return meta


class CreateIndexIfNotExists(CreateIndex):
    """
    The class will skip creating indexes if they already exists and would setup indexes if they don't exist.
    The utility of this class is in initializing the elasticsearch migrations
    for the environments that already have live HQ indexes.

    Because of the nature of the operation, this class is not integrated into `make_elastic_migration` command.
    This class should to be manually added to the bootstrap migrations and
    it should be ensured that the index names are identical to live indexes.

    Lets take an example of bootstrapping a running groups index

        - Generate boilerplate migrations with `make_elastic_migration`

            ```
            ./manage.py make_elastic_migration --name init_groups -c groups
            ```

        - The above command will generate a migration file let say 0001_init_groups.py

        - Replace the index name passed into CreateIndex in operations with the one that is running on HQ.

        - Replace `corehq.apps.es.migration_operations.CreateIndex` with
        `CreateIndexIfNotExists`

    """
    def run(self, *args, **kwargs):
        if self.es_versions and self._should_skip_operation(self.es_versions):
            return
        from corehq.apps.es.client import manager
        if not manager.index_exists(self.name):
            return super().run(*args, **kwargs)
        log.info(f"ElasticSearch index {self.name} already exists. Skipping create index operation.")

    def reverse_run(self, *args, **kw):
        return None


class MappingUpdateFailed(Exception):
    """The mapping update operation failed."""
