import datetime

import mock
from django.test import SimpleTestCase
from freezegun import freeze_time

from soil.progress import ProgressManager


@mock.patch.object(ProgressManager, '_set_task_progress')
class ProgressManagerTest(SimpleTestCase):

    def test_basic(self, set_task_progress):
        total = 100000
        delta = .1  # seconds
        task = object()
        flushes = []
        set_task_progress.side_effect = lambda task, current, total: flushes.append(
            [(frozen_time() - start_time).total_seconds(), task, current, total])

        with freeze_time("2020-04-20", as_arg=True) as frozen_time:
            start_time = frozen_time()
            with ProgressManager(task) as progress_manager:
                for i in range(1, total + 1):
                    progress_manager.set_progress(i, total)
                    frozen_time.tick(delta=delta)

        # Uncomment the following code to generate the expected value
        #     for time_passed, _, current, total in flushes:
        #         print(f'            [{time_passed}, task, {current}, {total}],')

        self.assertEqual(flushes, [
            # starts right away
            [0.0, task, 1, 100000],
            # first delay is .5s (min_interval)
            [0.5, task, 6, 100000],
            # each delay after is the last delay * 1.2
            # (0.5 * 1.2 = .6; .5 + .6 = 1.1)
            [1.1, task, 12, 100000],
            [1.9, task, 20, 100000],
            [2.7, task, 28, 100000],
            [3.8, task, 39, 100000],
            [5.0, task, 51, 100000],
            [6.5, task, 66, 100000],
            [8.3, task, 84, 100000],
            [10.4, task, 105, 100000],
            [13.0, task, 131, 100000],
            [16.1, task, 162, 100000],
            [19.8, task, 199, 100000],
            [24.3, task, 244, 100000],
            [29.6, task, 297, 100000],
            [36.1, task, 362, 100000],
            [43.8, task, 439, 100000],
            [53.0, task, 531, 100000],
            [64.1, task, 642, 100000],
            [77.4, task, 775, 100000],
            [93.4, task, 935, 100000],
            [112.6, task, 1127, 100000],
            [135.6, task, 1357, 100000],
            [163.2, task, 1633, 100000],
            [196.3, task, 1964, 100000],
            [236.0, task, 2361, 100000],
            [283.7, task, 2838, 100000],
            [341.0, task, 3411, 100000],
            [409.7, task, 4098, 100000],
            [492.1, task, 4922, 100000],
            [591.0, task, 5911, 100000],
            [709.7, task, 7098, 100000],
            [852.1, task, 8522, 100000],
            [1023.0, task, 10231, 100000],
            [1228.1, task, 12282, 100000],
            [1474.2, task, 14743, 100000],
            [1769.6, task, 17697, 100000],
            [2124.0, task, 21241, 100000],
            [2549.2, task, 25493, 100000],
            # 600s = 10m interval going forward (max_interval)
            [3059.6, task, 30597, 100000],
            [3659.6, task, 36597, 100000],
            [4259.6, task, 42597, 100000],
            [4859.6, task, 48597, 100000],
            [5459.6, task, 54597, 100000],
            [6059.6, task, 60597, 100000],
            [6659.6, task, 66597, 100000],
            [7259.6, task, 72597, 100000],
            [7859.6, task, 78597, 100000],
            [8459.6, task, 84597, 100000],
            [9059.6, task, 90597, 100000],
            [9659.6, task, 96597, 100000],
            # flush the last update on __exit__
            [10000.0, task, 100000, 100000],
            # 10,000 updates with only 52 flushes (instead of 10,000)
        ])
