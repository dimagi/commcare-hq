

class WarehouseTable(object):

    @classmethod
    def commit(cls, batch_id, start_datetime, end_datetime):
        '''
        Commits records based on a time frame.

        :param batch_id: The id of the batch being committed
        :param start_datetime: A python datetime denoting the start of the interval (exclusive)
        :param end_datetime: A python datetime denoting the end of the interval (inclusive)

        :returns: True if commit passed validations, False otherwise
        '''
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        '''Returns a list of slugs that the warehouse table is dependent on'''
        raise NotImplementedError
