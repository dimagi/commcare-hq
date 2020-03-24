class Parser(object):
    def __init__(self, worksheet, location_types):
        self.transitions = {}
        self.errors = {}

    def parse(self):
        return self.transitions, self.errors
