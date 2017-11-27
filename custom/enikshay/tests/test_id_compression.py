from builtins import range
from ..user_setup import compress_id


def test_compression():
    growth = "HLJXYUWMNV"
    gb = len(growth)
    lead = "ACE3459KFPRT"
    lb = len(lead)
    body = "ACDEFHJKLMNPQRTUVWXY3479"
    bb = len(body)

    def check(serial_id, expected, body_count):
        actual = compress_id(serial_id, growth, lead, body, body_count)
        msg = "'{}' compresses to '{}' instead of the expected '{}'".format(
            serial_id, actual, expected)
        assert actual == expected, msg

    for serial_id, expected, body_count in [
        (0, 'AAA', 2),
        ((lb * bb * bb) - 1, 'T99', 2),
        ((lb * bb * bb), 'LAAA', 2),
        ((gb * lb * bb * bb) - 1, "VT99", 2),
        ((gb * lb * bb * bb), "LHAAA", 2),
        ((gb * gb * lb * bb * bb) - 1, 'VVT99', 2),
        (0, 'A', 0),
        (11, 'T', 0),
        (12, 'LA', 0),
        (119, 'VT', 0),
    ]:
        yield check, serial_id, expected, body_count


def test_no_overlap():
    generated_ids = set()
    growth = "123"
    lead = "ABC"
    body = "ABC12345"
    for i in range(100):
        ipart = compress_id(i, growth, lead, body, 1)
        for j in range(100):
            jpart = compress_id(j, growth, lead, body, 1)
            for k in range(100):
                kpart = compress_id(k, growth, lead, body, 1)
                generated_id = ipart + jpart + kpart
                assert generated_id not in generated_ids
                generated_ids.add(generated_id)
