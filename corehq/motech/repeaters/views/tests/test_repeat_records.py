from corehq.motech.repeaters.views import repeat_records
from unittest.mock import Mock

_base_strings = [
    None,
    '',
    'repeater=&record_state=&payload_id=payload_3',
    'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
    'repeater=&record_state=&payload_id=',
    'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
    'repeater=&record_state=STATUS&payload_id=payload_2',
    'repeater=repeater_2&record_state=STATUS&payload_id=',
]


def test__get_records():
    request = Mock()
    request.POST.get.side_effect = [None, '', 'id_1 id_2 ', 'id_1 id_2', ' id_1 id_2 ']
    expected_records_ids = [
        [],
        [],
        ['id_1', 'id_2'],
        ['id_1', 'id_2'],
        ['', 'id_1', 'id_2'],
    ]

    records_ids = repeat_records._get_records(None)
    assert records_ids == []

    for r in range(4):
        records_ids = repeat_records._get_records(request)
        assert records_ids == expected_records_ids[r]


def test__get_query():
    request = Mock()
    request.POST.get.side_effect = [None, 'a=1&b=2']
    expected_queries = ['', 'a=1&b=2']

    query = repeat_records._get_query(None)
    assert query == ''

    for r in range(2):
        records_ids = repeat_records._get_query(request)
        assert records_ids == expected_queries[r]


def test__get_flag():
    request = Mock()
    request.POST.get.side_effect = [None, 'flag']
    expected_flags = ['', 'flag']

    flag = repeat_records._get_flag(None)
    assert flag == ''

    for r in range(2):
        records_ids = repeat_records._get_flag(request)
        assert records_ids == expected_flags[r]


def test__change_record_state():
    strings_to_add = [
        'NO_STATUS',
        'NO_STATUS',
        None,
        '',
        'STATUS',
        'STATUS_2',
        'STATUS_3',
        'STATUS_4',
    ]
    desired_strings = [
        '',
        '',
        'repeater=&record_state=&payload_id=payload_3',
        'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
        'repeater=&record_state=STATUS&payload_id=',
        'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
        'repeater=&record_state=STATUS_3&payload_id=payload_2',
        'repeater=repeater_2&record_state=STATUS_4&payload_id=',
    ]

    for r in range(len(desired_strings)):
        returned_string = repeat_records._change_record_state(_base_strings[r], strings_to_add[r])
        assert returned_string == desired_strings[r]


def test__url_parameters_to_dict():
    desired_dicts = [
        {},
        {},
        {'repeater': '', 'record_state': '', 'payload_id': 'payload_3'},
        {'repeater': 'repeater_3', 'record_state': 'STATUS_2', 'payload_id': 'payload_2'},
        {'repeater': '', 'record_state': '', 'payload_id': ''},
        {'repeater': 'repeater_1', 'record_state': 'STATUS_2', 'payload_id': 'payload_1'},
        {'repeater': '', 'record_state': 'STATUS', 'payload_id': 'payload_2'},
        {'repeater': 'repeater_2', 'record_state': 'STATUS', 'payload_id': ''},
    ]

    for r in range(len(desired_dicts)):
        returned_dict = repeat_records._url_parameters_to_dict(_base_strings[r])
        assert returned_dict == desired_dicts[r]


def test__schedule_task_with_flag():
    pass


def test__schedule_task_without_flag():
    pass
