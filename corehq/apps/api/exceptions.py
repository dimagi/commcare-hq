class InvalidUpdateRequest(Exception):

    def __init__(self, illegal_fields):
        self.illegal_fields = illegal_fields

    def __str__(self):
        return f'Cannot update the key(s) {", ".join(self.illegal_fields)}.'
