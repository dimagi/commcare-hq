from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict


class TrackRelatedChanges(object):

    def __init__(self):
        self.create_models = defaultdict(list)
        self.update_models = defaultdict(list)
        self.delete_models = defaultdict(list)

    def has_tracked_models(self, model_class=None):
        return any((
            self.has_tracked_models_to_create(model_class),
            self.has_tracked_models_to_update(model_class),
            self.has_tracked_models_to_delete(model_class)
        ))

    def has_tracked_models_to_delete(self, model_class=None):
        return self._has_tracked_models(self.delete_models, model_class)

    def has_tracked_models_to_update(self, model_class=None):
        return self._has_tracked_models(self.update_models, model_class)

    def has_tracked_models_to_create(self, model_class=None):
        return self._has_tracked_models(self.create_models, model_class)

    def _has_tracked_models(self, storage, model_class=None):
        if model_class:
            return bool(storage[model_class])
        return any(models for models in storage.values())

    def clear_tracked_models(self, model_class=None):
        if not model_class:
            self.create_models.clear()
            self.update_models.clear()
            self.delete_models.clear()
        else:
            self.create_models[model_class] = []
            self.update_models[model_class] = []
            self.delete_models[model_class] = []
        self.on_tracked_models_cleared(model_class)

    def on_tracked_models_cleared(self, model_class=None):
        """
        Override this to be notified when tracked models have been cleared.
        :param model_class: May be None which indicates that all types have been cleared.
        """
        pass

    def track_create(self, model):
        self.create_models[model.__class__].append(model)

    def track_update(self, model):
        self.update_models[model.__class__].append(model)

    def track_delete(self, model):
        self.delete_models[model.__class__].append(model)

    def get_live_tracked_models(self, model_class):
        """Return tracked models that have not been deleted
        """
        return self.update_models[model_class] + self.create_models[model_class]

    def get_tracked_models_to_create(self, model_class):
        return self.create_models[model_class]

    def get_tracked_models_to_update(self, model_class):
        return self.update_models[model_class]

    def get_tracked_models_to_delete(self, model_class):
        return self.delete_models[model_class]
