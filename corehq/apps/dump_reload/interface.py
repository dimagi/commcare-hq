import gzip
import os
import re
import sys
import warnings
from abc import ABCMeta, abstractmethod, abstractproperty

from corehq.util.log import with_progress_bar


class DataDumper(metaclass=ABCMeta):
    """
    :param domain: Name of domain to dump data for
    :param excludes: List of app labels ("app_label.model_name" or "app_label") to exclude
    :param includes: List of app labels ("app_label.model_name" or "app_label") to include
    """

    @abstractproperty
    def slug(self):
        raise NotImplementedError

    def __init__(self, domain, excludes, includes, stdout=None, stderr=None):
        self.domain = domain
        self.excludes = excludes
        self.includes = includes
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


class DataLoader(metaclass=ABCMeta):
    def __init__(self, object_filter=None, stdout=None, stderr=None, chunksize=None, should_throttle=False):
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.object_filter = re.compile(object_filter, re.IGNORECASE) if object_filter else None
        self.chunksize = chunksize
        self.should_throttle = should_throttle

    @abstractproperty
    def slug(self):
        raise NotImplementedError

    @abstractmethod
    def load_objects(self, object_strings, force=False, dry_run=False):
        """
        :param object_strings: iterable of JSON encoded object strings
        :param force: True if objects should be loaded into an existing domain
        :return: loaded object Counter
        """
        raise NotImplementedError

    def load_from_path(self, extracted_dump_path, dump_meta, force=False, dry_run=False):
        loaded_object_count = {}
        for file in os.listdir(extracted_dump_path):
            path = os.path.join(extracted_dump_path, file)
            if file.startswith(self.slug) and file.endswith('.gz') and os.path.isfile(path):
                counts = self.load_from_file(path, dump_meta, force, dry_run)
                loaded_object_count.update(counts)
        return loaded_object_count

    def load_from_file(self, file_path, dump_meta, force=False, dry_run=False):
        if not os.path.isfile(file_path):
            raise Exception("Dump file not found: {}".format(file_path))

        self.stdout.write(f"\nLoading {file_path} using '{self.slug}' data loader.")
        meta_slug, _ = os.path.splitext(os.path.basename(file_path))
        expected_count = sum(dump_meta[meta_slug].values())
        with gzip.open(file_path) as dump_file:
            object_strings = with_progress_bar(dump_file, length=expected_count)
            loaded_object_count = self.load_objects(object_strings, force, dry_run)

        # Warn if the file we loaded contains 0 objects.
        if sum(loaded_object_count.values()) == 0:
            warnings.warn(
                "No data found for '%s'. (File format may be "
                "invalid.)" % file_path,
                RuntimeWarning
            )

        return {meta_slug: loaded_object_count}
