import logging
from datetime import datetime

from django.db.migrations import RunPython

from corehq.apps.es.index.settings import render_index_tuning_settings

log = logging.getLogger(__name__)


class BaseElasticOperation(RunPython):
    """Perform an operation for an Elasticsearch index."""

    def run(self, *args, **kw):
        raise NotImplementedError(type(self).__name__)

    def reverse_run(self, *args, **kw):
        raise NotImplementedError(type(self).__name__)

    def __repr__(self):
        return f"<{type(self).__name__} index={self.name!r}>"


class CreateIndex(BaseElasticOperation):
    """Create an Elasticsearch index."""

    def __init__(self, name, type_, mapping, analysis, settings_key, comment=None):
        """CreateIndex operation.

        :param name: the name of the index to be created.
        :param type_: the index ``_type`` for the mapping.
        :param mapping: the mapping to apply to the new index.
        :param analysis: the analysis configuration to apply to the new index
        :param settings_key: the index settings key to use for rendering
            tuning settings.
        :param comment: Optional value to set on the index's
            ``mapping._meta.comment`` property.
        """
        super().__init__(self.run, self.reverse_run)
        self.name = name
        self.type = type_
        self.mapping = mapping
        self.analysis = analysis
        self.settings_key = settings_key
        self.comment = comment

    def run(self, *args, **kw):
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
        DeleteIndex(self.name).run(*args, **kw)

    def describe(self):
        return f"Create Elasticsearch index {self.name!r}"

    @staticmethod
    def render_index_metadata(type_, mapping, analysis, settings_key, comment):
        # NOTE: mapping might be JsonObject.DictProperty, handle with care
        mapping = dict(mapping)
        mapping["_meta"] = dict(mapping.pop("_meta", {}))
        mapping["_meta"]["created"] = datetime.isoformat(datetime.utcnow())
        if comment:
            mapping["_meta"]["comment"] = comment
        settings = {"analysis": analysis}
        settings.update(render_index_tuning_settings(settings_key))
        return {
            "mappings": {type_: mapping},
            "settings": settings,
        }


class DeleteIndex(BaseElasticOperation):
    """Delete an Elasticsearch index."""

    def __init__(self, name, reverse_params=None):
        """DeleteIndex operation.

        :param name: the name of the index to be deleted.
        :param reverse_params: an iterable of four items containing ``(type,
            mapping, analysis, settings_key)`` for reversing the migration. If
            ``None`` (the default), the operation is irreversible.
        """
        super().__init__(self.run, self.reverse_run if reverse_params else None)
        self.name = name
        if reverse_params:
            type_, mapping, analysis, settings_key = reverse_params
            self.reverse_type = type_
            self.reverse_mapping = mapping
            self.reverse_analysis = analysis
            self.reverse_settings_key = settings_key

    def run(self, *args, **kw):
        from corehq.apps.es.client import manager
        log.info("Deleting Elasticsearch index: %s" % self.name)
        manager.index_delete(self.name)

    def reverse_run(self, *args, **kw):
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
