from unittest.mock import Mock

from corehq.apps.project_db.case_adapter import case_to_row_dict


def _make_case(case_json=None, live_indices=None, **fields):
    case = Mock()
    case.case_id = fields.get('case_id', 'abc123')
    case.owner_id = fields.get('owner_id', 'owner1')
    case.name = fields.get('name', 'Test Case')
    case.opened_on = fields.get('opened_on', '2025-01-01')
    case.closed_on = fields.get('closed_on', None)
    case.modified_on = fields.get('modified_on', '2025-06-01')
    case.closed = fields.get('closed', False)
    case.external_id = fields.get('external_id', '')
    case.server_modified_on = fields.get('server_modified_on', '2025-06-01')
    case.case_json = case_json or {}
    case.live_indices = live_indices or []
    return case


def _make_index(identifier, referenced_id):
    index = Mock()
    index.identifier = identifier
    index.referenced_id = referenced_id
    return index


def test_fixed_fields_extracted():
    case = _make_case(
        case_id='abc123',
        owner_id='owner1',
        name='My Case',
        opened_on='2025-01-01',
        closed_on='2025-03-01',
        modified_on='2025-06-01',
        closed=True,
        external_id='ext-1',
        server_modified_on='2025-06-02',
    )
    result = case_to_row_dict(case)

    assert result['case_id'] == 'abc123'
    assert result['owner_id'] == 'owner1'
    assert result['case_name'] == 'My Case'
    assert result['opened_on'] == '2025-01-01'
    assert result['closed_on'] == '2025-03-01'
    assert result['modified_on'] == '2025-06-01'
    assert result['closed'] is True
    assert result['external_id'] == 'ext-1'
    assert result['server_modified_on'] == '2025-06-02'


def test_dynamic_properties_from_case_json():
    case = _make_case(case_json={'color': 'red', 'size': 'large'})
    result = case_to_row_dict(case)

    assert result['color'] == 'red'
    assert result['size'] == 'large'


def test_indices_extracted():
    indices = [
        _make_index('parent', 'parent-case-id'),
        _make_index('host', 'host-case-id'),
    ]
    case = _make_case(live_indices=indices)
    result = case_to_row_dict(case)

    assert result['indices'] == {
        'parent': 'parent-case-id',
        'host': 'host-case-id',
    }


def test_empty_case_json_no_extra_keys():
    case = _make_case(case_json={})
    result = case_to_row_dict(case)

    expected_keys = {
        'case_id', 'owner_id', 'case_name', 'opened_on', 'closed_on',
        'modified_on', 'closed', 'external_id', 'server_modified_on',
        'indices',
    }
    assert set(result.keys()) == expected_keys


def test_no_live_indices_gives_empty_dict():
    case = _make_case(live_indices=[])
    result = case_to_row_dict(case)

    assert result['indices'] == {}
