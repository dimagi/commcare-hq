from itertools import islice


class ResumableIteratorWrapper:
    def __init__(self, sequence_factory_fn, get_element_properties_fn=None, limit=None):
        self.limit = limit

        # if a limit exists, increase it by 1 to allow us to check whether additional items remain at the end
        padded_limit = limit + 1 if limit else None
        self.original_it = iter(sequence_factory_fn(padded_limit))
        self.it = islice(self.original_it, self.limit)
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
            if self.limit and not self.is_complete:
                # the end of the limited sequence was reached, check if items beyond the limit remain
                try:
                    next(self.original_it)
                except StopIteration:
                    # the iteration is fully complete -- no additional items can be fetched
                    self.is_complete = True
            else:
                self.is_complete = True
            raise

        return self.prev_element

    def get_next_query_params(self):
        if self.is_complete:
            return None
        if not self.iteration_started:
            return {}

        return self.get_element_properties_fn(self.prev_element)
