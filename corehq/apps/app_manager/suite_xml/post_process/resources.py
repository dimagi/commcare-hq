from collections import Counter
from django.db import models

from corehq.apps.app_manager.exceptions import ResourceOverrideError
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.sections.resources import FormResourceContributor
from corehq.apps.app_manager.suite_xml.xml_models import XFormResource
from corehq.util.quickcache import quickcache


class ResourceOverride(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    # Type of resource, e.g., xform. Populated by the root_name of the relevant suite_xml.xml_models class.
    root_name = models.CharField(max_length=32, null=False)
    pre_id = models.CharField(max_length=255, null=False)
    post_id = models.CharField(max_length=255, null=False)

    class Meta(object):
        unique_together = ('domain', 'app_id', 'root_name', 'pre_id')


def add_xform_resource_overrides(domain, app_id, pre_to_post_map):
    overrides_by_pre_id = get_xform_resource_overrides(domain, app_id)
    errors = []
    new_overrides = []

    for pre_id, post_id in pre_to_post_map.items():
        if pre_id in overrides_by_pre_id:
            if post_id != overrides_by_pre_id[pre_id].post_id:
                errors.append("Attempt to change {} from {} to {}".format(
                    pre_id,
                    overrides_by_pre_id[pre_id].post_id,
                    post_id
                ))
        else:
            new_overrides.append(ResourceOverride(
                domain=domain,
                app_id=app_id,
                root_name=XFormResource.ROOT_NAME,
                pre_id=pre_id,
                post_id=post_id,
            ))

    if new_overrides and not errors:
        ResourceOverride.objects.bulk_create(new_overrides)
        get_xform_resource_overrides.clear(domain, app_id)

    if errors:
        raise ResourceOverrideError("""
            Cannot update overrides for domain {}, app {}, errors:\n{}
        """.strip().format(domain, app_id, "\n".join(["\t{}".format(e) for e in errors])))


@quickcache(['domain', 'app_id'], timeout=1 * 60 * 60)
def get_xform_resource_overrides(domain, app_id):
    return {
        override.pre_id: override
        for override in ResourceOverride.objects.filter(
            domain=domain,
            app_id=app_id,
            root_name=XFormResource.ROOT_NAME,
        )
    }


class ResourceOverrideHelper(PostProcessor):

    def update_suite(self):
        """
        Applies manual overrides of resource ids.
        """
        overrides_by_pre_id = get_xform_resource_overrides(self.app.domain, self.app.master_id)
        resources = getattr(self.suite, FormResourceContributor.section_name)
        for resource in resources:
            if resource.id in overrides_by_pre_id:
                resource.id = overrides_by_pre_id[resource.id].post_id

        id_counts = Counter(resource.id for resource in resources)
        duplicates = [key for key, count in id_counts.items() if count > 1]
        if duplicates:
            raise ResourceOverrideError("Duplicate resource ids found: {}".format(", ".join(duplicates)))
