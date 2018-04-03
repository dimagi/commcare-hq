from __future__ import absolute_import


from __future__ import unicode_literals
def get_by_domain_and_type(domain, field_type):
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition

    return CustomDataFieldsDefinition.view(
        'custom_data_fields/by_field_type',
        key=[domain, field_type],
        include_docs=True,
        reduce=False,
        # if there's more than one,
        # it's probably because a few were created at the same time
        # due to a race condition
        limit=1,
    ).one()
