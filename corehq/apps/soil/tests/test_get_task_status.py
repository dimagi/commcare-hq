import datetime

from django.test import SimpleTestCase, override_settings

from soil.progress import get_task_status, TaskStatus, TaskProgress, STATES


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
class GetTaskStatusTest(SimpleTestCase):
    def test_missing(self):
        self.assertEqual(get_task_status(self.MockTask(
            task_meta={
                'date_done': None,
                'result': None,
                'status': 'PENDING',
                'task_args': None,
                'task_id': 'obviously fake!',
                'task_kwargs': None,
                'task_name': None,
                'traceback': None
            }
        )), TaskStatus(
            result=None,
            error=None,
            exception=None,
            state=STATES.missing,
            progress=TaskProgress(
                current=None,
                total=None,
                percent=None,
                error=False,
                error_message=''
            )
        ))

    def test_not_missing(self):
        self.assertEqual(get_task_status(self.MockTask(
            task_meta={
                'children': [],
                'date_done': datetime.datetime(2020, 4, 7, 14, 37, 1, 926615),
                'result': {'current': 17076, 'total': 10565489},
                'status': 'PROGRESS',
                'task_args': None,
                'task_id': '2243626c-f725-442e-b257-b018a0860d1b',
                'task_kwargs': None,
                'task_name': None,
                'traceback': None
            }
        )), TaskStatus(
            result=None,
            error=None,
            exception=None,
            state=STATES.started,
            progress=TaskProgress(
                current=17076,
                total=10565489,
                percent=100 * 17076 // 10565489,
                error=False,
                error_message=''
            )
        ))

    class MockTask(object):
        def __init__(self, task_meta, failed=False, successful=False):
            self.__task_meta = task_meta
            self.__failed = failed
            self.__successful = successful

        def _get_task_meta(self):
            return self.__task_meta

        def failed(self):
            return self.__failed

        def successful(self):
            return self.__successful

        @property
        def status(self):
            return self.__task_meta.get('status')

        state = status

        @property
        def result(self):
            return self.__task_meta.get('result')

        info = result
