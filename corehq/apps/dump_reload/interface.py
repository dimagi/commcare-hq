from __future__ import absolute_import
from __future__ import unicode_literals
import gzip
import os
import warnings
from abc import ABCMeta, abstractmethod, abstractproperty

import six
import sys


class DataDumper(six.with_metaclass(ABCMeta)):
    """
    :param domain: Name of domain to dump data for
    :param excludes: List of app labels ("app_label.model_name" or "app_label") to exclude
    """

    @abstractproperty
    def slug(self):
        raise NotImplementedError

    def __init__(self, domain, excludes, stdout=None, stderr=None):
        self.domain = domain
        self.excludes = excludes
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

    @abstractmethod
    def dump(self, output_stream):
        """
        Dump data for domain to stream.
        :param output_stream: Stream to write json encoded objects to
        :return: Counter object with keys being app model labels and values being number of models dumped
        """
        raise NotImplementedError


class DataLoader(six.with_metaclass(ABCMeta)):
    def __init__(self, stdout=None, stderr=None):
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

    @abstractproperty
    def slug(self):
        raise NotImplementedError

    @abstractmethod
    def load_objects(self, object_strings, force=False):
        """
        :param object_strings: iterable of JSON encoded object strings
        :param force: True if objects should be loaded into an existing domain
        :return: tuple(total object count, loaded object count)
        """
        raise NotImplementedError

    def load_from_file(self, extracted_dump_path, force=False):
        file_path = os.path.join(extracted_dump_path, '{}.gz'.format(self.slug))
        if not os.path.isfile(file_path):
            raise Exception("Dump file not found: {}".format(file_path))

        with gzip.open(file_path) as dump_file:
            total_object_count, loaded_object_count = self.load_objects(dump_file, force)

        # Warn if the file we loaded contains 0 objects.
        if sum(loaded_object_count.values()) == 0:
            warnings.warn(
                "No data found for '%s'. (File format may be "
                "invalid.)" % file_path,
                RuntimeWarning
            )

        return total_object_count, loaded_object_count
