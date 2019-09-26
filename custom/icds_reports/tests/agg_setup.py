from corehq.apps.locations.models import SQLLocation, LocationType


def setup_location_hierarchy(domain_name):
    SQLLocation.objects.all().delete()
    LocationType.objects.all().delete()
    state_location_type = LocationType.objects.create(
        domain=domain_name,
        name='state',
    )
    st1 = SQLLocation.objects.create(
        domain=domain_name,
        name='st1',
        location_id='st1',
        location_type=state_location_type
    )
    st2 = SQLLocation.objects.create(
        domain=domain_name,
        name='st2',
        location_id='st2',
        location_type=state_location_type
    )
    st3 = SQLLocation.objects.create(
        domain=domain_name,
        name='st3',
        location_id='st3',
        location_type=state_location_type
    )
    st4 = SQLLocation.objects.create(
        domain=domain_name,
        name='st4',
        location_id='st4',
        location_type=state_location_type
    )
    st5 = SQLLocation.objects.create(
        domain=domain_name,
        name='st5',
        location_id='st5',
        location_type=state_location_type
    )
    st6 = SQLLocation.objects.create(
        domain=domain_name,
        name='st6',
        location_id='st6',
        location_type=state_location_type
    )
    st7 = SQLLocation.objects.create(
        domain=domain_name,
        name='st7',
        location_id='st7',
        location_type=state_location_type
    )
    # exercise the logic that excludes test states by creating one
    test_state = SQLLocation.objects.create(
        domain=domain_name,
        name='test_state',
        location_id='test_state',
        location_type=state_location_type,
        metadata={
            'is_test_location': 'test',
        }
    )

    district_location_type = LocationType.objects.create(
        domain=domain_name,
        name='district',
        parent_type=state_location_type,
    )
    d1 = SQLLocation.objects.create(
        domain=domain_name,
        name='d1',
        location_id='d1',
        location_type=district_location_type,
        parent=st1
    )

    block_location_type = LocationType.objects.create(
        domain=domain_name,
        name='block',
        parent_type=district_location_type,
    )
    b1 = SQLLocation.objects.create(
        domain=domain_name,
        name='b1',
        location_id='b1',
        location_type=block_location_type,
        parent=d1
    )

    supervisor_location_type = LocationType.objects.create(
        domain=domain_name,
        name='supervisor',
        parent_type=state_location_type,
    )
    s1 = SQLLocation.objects.create(
        domain=domain_name,
        name='s1',
        location_id='s1',
        location_type=supervisor_location_type,
        parent=b1,
    )

    awc_location_type = LocationType.objects.create(
        domain=domain_name,
        name='awc',
        parent_type=supervisor_location_type,
    )
    a7 = SQLLocation.objects.create(
        domain=domain_name,
        name='a7',
        location_id='a7',
        location_type=awc_location_type,
        parent=s1,
    )
