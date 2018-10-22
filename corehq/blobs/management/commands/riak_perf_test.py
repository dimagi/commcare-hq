from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import time
from io import open
from multiprocessing import Process, Queue
from os import listdir
from os.path import isfile, join

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host
from django.conf import settings
from django.core.management.base import BaseCommand
from six.moves import range

from corehq.blobs.s3db import is_not_found

NUM_PROCESSES = 8


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'data-path',
            help='Path to folder containing test data',
        )
        parser.add_argument(
            'db',
            choices=['old',  'new'],
        )
        parser.add_argument(
            '--read',
            action='store_true',
            default=True
        )
        parser.add_argument(
            '--write',
            action='store_true',
            default=True
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            default=True
        )

    def handle(self, *args, **options):
        data_path = options['data-path']
        db = options['db']
        file_list = [f for f in listdir(data_path) if isfile(join(data_path, f))]

        if db == 'old':
            config = settings.OLD_S3_BLOB_DB_SETTINGS
        else:
            config = settings.S3_BLOB_DB_SETTINGS

        kwargs = {}
        if "config" in config:
            kwargs["config"] = Config(**config["config"])
        db = boto3.resource(
            's3',
            endpoint_url=config.get("url"),
            aws_access_key_id=config.get("access_key", ""),
            aws_secret_access_key=config.get("secret_key", ""),
            **kwargs
        )
        db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

        try:
            db.meta.client.head_bucket(Bucket='blobdbtest')
        except ClientError as err:
            if not is_not_found(err):
                raise
            db.create_bucket(Bucket='blobdbtest')

        bucket = db.Bucket('blobdbtest')

        queue = Queue(150)
        workers = []
        for i in range(NUM_PROCESSES):
            w = Worker(i, queue, bucket, options['read'], options['write'], options['delete'])
            workers.append(w)
            w.start()

        total = len(file_list)
        count = 0
        msg = "Found %s documents" % (total)
        print(msg)

        for file_path in file_list:
            count += 1
            queue.put((join(data_path, file_path), count))

        # shutdown workers
        for i in range(NUM_PROCESSES):
            queue.put(None)

        for worker in workers:
            worker.join()

        times = {
            'read': [],
            'write': [],
            'delete': [],
        }
        for i in range(NUM_PROCESSES):
            for key in times:
                with open('timings_{}_{}.log'.format(i, key)) as f:
                    times[key].extend([float(t.strip()) for t in f.readlines()])

        for key, time_list in times.items():
            print("{} ({})".format(key, len(time_list)))
            print('    Max: {}'.format(max(time_list)))
            print('    Min: {}'.format(min(time_list)))
            print('    Avg: {}'.format(sum(time_list)/len(time_list)))


class Worker(Process):

    def __init__(self, worker_num, queue, s3_bucket, read=True, write=True, delete=True):
        super(Worker, self).__init__()
        self.worker_num = worker_num
        self.delete = delete
        self.write = write
        self.read = read
        self.s3_bucket = s3_bucket
        self.queue = queue
        self.times = {
            'read': [],
            'write': [],
            'delete': [],
        }

    def run(self):
        for path, count in iter(self.queue.get, None):
            key = path.split('/')[-1]

            if self.write:
                with Timer(self, 'write'):
                    self.write_blob(key, path)
            if self.read:
                with Timer(self, 'read'):
                    self.read_blob(key)
            if self.delete:
                with Timer(self, 'delete'):
                    self.delete_blob(key)

        self._flush_timing()

    def write_blob(self, key, path):
        try:
            with open(path, 'r') as f:
                self.s3_bucket.upload_fileobj(f, key)
        except Exception as e:
            print("     Write %s failed! Error is: %s %s" % (key, e.__class__.__name__, e))

    def read_blob(self, key):
        try:
            resp = self.s3_bucket.Object(key).get()
            resp["Body"].read()
        except Exception as e:
            print("     Read %s failed! Error is: %s %s" % (key, e.__class__.__name__, e))

    def delete_blob(self, key):
        try:
            obj = self.s3_bucket.Object(key)
            obj.delete()
        except Exception as e:
            print("     Delete %s failed! Error is: %s %s" % (key, e.__class__.__name__, e))

    def record_timing(self, bucket, duration):
        self.times[bucket].append(duration)
        for key, times in self.times.items():
            if len(times) >= 100:
                self._flush_timing()
                return

    def _flush_timing(self):
        times = self.times.copy()
        self.times = {
            'read': [],
            'write': [],
            'delete': [],
        }
        print('Flushing timings for worker {}'.format(self.worker_num))
        for key, times in times.items():
            with open('timings_{}_{}.log'.format(self.worker_num, key), 'a') as f:
                f.writelines(["{}\n".format(t) for t in times])


class Timer(object):
    def __init__(self, worker, bucket):
        self.bucket = bucket
        self.worker = worker

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.time()
        self.worker.record_timing(self.bucket, end - self.start)
