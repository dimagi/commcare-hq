class ObjectTestAssertionError(Exception):
    def __init__(self, actual, expected, diff):
        super().__init__()
        self.actual = actual
        self.expected = expected
        self.diff = diff

    def __str__(self):
        return f"Assertion failed: {self.actual} != {self.expected}"
