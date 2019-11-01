class Dhis2Exception(Exception):
    def __init__(self, domain, base_url, username, *args):
        self.domain = domain
        self.base_url = base_url
        self.username = username
        super().__init__(*args)

    def __str__(self):
        string = super().__str__()
        return f'{self.domain}: {self.username}@{self.base_url}: {string}'


class BadTrackedEntityInstanceID(Dhis2Exception):
    """
    A Tracked Entity instance ID was not found on the server that (is
    believed to have) issued it.
    """
    pass


class MultipleInstancesFound(Dhis2Exception):
    """
    Unable to select a corresponding Tracked Entity instance from
    multiple available candidates.
    """
    pass
