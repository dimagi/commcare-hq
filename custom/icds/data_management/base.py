class DataManagement(object):
    slug = ""

    def run(self):
        raise NotImplementedError


class SQLBasedDataManagement(DataManagement):
    def run(self):
        """
        iterate sql records and update them as and when needed
        """
        pass


class ESBasedDataManagement(DataManagement):
    def run(self):
        """
        find records to be updated via ES and then update them
        """
        pass
