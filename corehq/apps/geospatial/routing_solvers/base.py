
class DisbursementAlgorithmSolverInterface:

    def __init__(self, request_json):
        self.request_json = request_json

    def solve(self, *args, **kwargs):
        """
        The solve method implementation should return either the results if it's readily
        available or a poll_id which can be used to poll for the results.
        If the results are available the poll_id is expected to be None and vice versa.
        :returns: a tuple formatted as (<poll_id>, <results>)
        """
        raise NotImplementedError()
