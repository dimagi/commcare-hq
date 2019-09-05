from collections import defaultdict
from unittest import TestCase

from corehq.blobs import CODES


class TestTypeCodes(TestCase):

    def test_uniqueness(self):
        names_by_code = defaultdict(set)
        for name, code in vars(CODES).items():
            if isinstance(code, int):
                names_by_code[code].add(name)
        conflicts = [tuple(x) for x in names_by_code.values() if len(x) > 1]
        self.assertFalse(conflicts, "type code conflicts: %s" % conflicts)
