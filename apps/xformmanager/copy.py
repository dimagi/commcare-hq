from __future__ import absolute_import

import copy

from django.db.models.query import CollectedObjects
from django.db.models import ForeignKey
from django.utils.datastructures import SortedDict

def collect_related(obj):
    """Collect all related objects to a single object by traversing
       ForgeignKeys.  Useful if you are about to delete something 
       and see what's being affected, or if you need to migrate a
       collection of objects.
    """
    collected_objs = CollectedObjects()
    obj._collect_sub_objects(collected_objs)
    return collected_objs 

def copy_related(collection):
    """
    Take in a CollectedObjects object and convert all the 
    query sets to explicit instantiations (copies) of the 
    objects.
    """
    to_return = SortedDict()
    for cls, objs in collection.items():
        copied_items = {}
        for pk, item in objs.items():
            # we only select one level deep, as we assume that everything
            # is only referencing things directly touching our objects
            copied_items[pk] = cls.objects.select_related(depth=1).get(pk=pk)
        to_return[cls] = copied_items
    return to_return

def prepare_migration_objects(obj):
    """
    Prepares migration object, to be consumed by the migrate() method
    below.  Call this when deleting/migrating an object if you'd like 
    to regenerate all it's related data post-deletion. 
    """
    class MigrationObjects(object):
        
        def __init__(self, obj):
            self.object = copy.copy(obj)
            self.model_class = type(obj)
            self.related_model_copies = copy_related(collect_related(obj))
             
    return MigrationObjects(obj)    

def migrate(migration_objects, new_obj, classes_not_to_touch=[]):
    """
    Migrate an old object from prepared migration objects.  Pass in
    the object prepared above and the new object to migrate to.  Optionally
    specify a set of classes not to touch during the migration.
    """
    # we traverse in reverse order, because that's how the dependency
    # chain works
    reversed_keys = migration_objects.related_model_copies.keys()
    reversed_keys.reverse()
    
    # the new classmap keys the old ids to the new objects.
    # this way we can properly traverse foreign key relationships.
    new_classmap = {migration_objects.model_class : {migration_objects.object.id: new_obj}}
    for cls in reversed_keys:
        if cls == migration_objects.model_class or cls in classes_not_to_touch:
            continue
        
        # pull out all the appropriate foreign key fields
        fks = [field for field in cls._meta.fields \
               if isinstance(field, ForeignKey) \
               and field.rel.to in migration_objects.related_model_copies \
               and not field.rel.to in classes_not_to_touch]
        
        object_list = migration_objects.related_model_copies[cls]
        new_classmap[cls] = {}
        for pk, obj in object_list.items():
            # blank out the pk/id and save to create new instances
            previous_id = obj.id
            obj.id = None
            for fk in fks:
                # set any relevant foreign keys to be the newly 
                # migrated objects
                fk_value = getattr(obj, "%s_id" % fk.name)
                if fk_value in migration_objects.related_model_copies[fk.rel.to]:
                    new_obj = new_classmap[fk.rel.to][fk_value]
                    setattr(obj, fk.name, new_obj)
            obj.save()
            
            # save the newly created object for future access
            new_classmap[cls][previous_id] = obj
            
    