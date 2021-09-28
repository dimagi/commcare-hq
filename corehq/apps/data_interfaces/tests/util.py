from corehq.apps.data_interfaces.models import AutomaticUpdateRule


def create_empty_rule(domain, workflow, case_type='person'):
    return AutomaticUpdateRule.objects.create(
        domain=domain,
        name='test',
        case_type=case_type,
        active=True,
        deleted=False,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        workflow=workflow,
    )
