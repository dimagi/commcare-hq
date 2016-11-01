from abc import ABCMeta, abstractmethod

import six


class DataDumper(six.with_metaclass(ABCMeta)):
    """
    :param domain: Name of domain to dump data for
    :param excludes: List of app labels ("app_label.model_name" or "app_label") to exclude
    """

    def __init__(self, domain, excludes):
        self.domain = domain
        self.excludes = excludes

    @abstractmethod
    def dump(self, output_stream):
        """
        Dump data for domain to stream.
        :param output_stream: Stream to write json encoded objects to
        :return: Counter object with keys being app model labels and values being number of models dumped
        """
        raise NotImplementedError


class DataLoader(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def load_objects(self, object_strings):
        """
        :param object_strings: iterable of JSON encoded object strings
        :return: tuple(total object count, loaded object count)
        """
        raise NotImplementedError
