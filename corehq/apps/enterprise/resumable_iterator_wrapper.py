class ResumableIteratorWrapper:
    def __init__(self, sequence, get_element_properties_fn=None):
        self.it = iter(sequence)
        self.prev_element = None
        self.iteration_started = False
        self.is_complete = False

        self.get_element_properties_fn = get_element_properties_fn
        if not self.get_element_properties_fn:
            self.get_element_properties_fn = lambda ele: {'value': ele}

    def __iter__(self):
        return self

    def __next__(self):
        self.iteration_started = True
        try:
            self.prev_element = next(self.it)
        except StopIteration:
            self.is_complete = True
            raise

        return self.prev_element

    def get_next_query_params(self):
        if self.is_complete:
            return None
        if not self.iteration_started:
            return {}

        return self.get_element_properties_fn(self.prev_element)
