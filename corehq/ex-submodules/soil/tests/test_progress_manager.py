import mock
from django.test import SimpleTestCase
from freezegun import freeze_time

import soil.progress
from soil.progress import TaskProgressManager


@mock.patch.object(soil.progress, 'set_task_progress')
class ProgressManagerTest(SimpleTestCase):

    def test_basic(self, set_task_progress):
        total = 100000
        delta = .1  # seconds
        task = object()
        flushes = []
        set_task_progress.side_effect = lambda task, current, total, src: flushes.append(
            [(frozen_time() - start_time).total_seconds(), task, current, total, src])

        with freeze_time("2020-04-20", as_arg=True) as frozen_time:
            start_time = frozen_time()
            with TaskProgressManager(task) as progress_manager:
                for i in range(1, total + 1):
                    progress_manager.set_progress(i, total)
                    frozen_time.tick(delta=delta)

        # Uncomment the following code to generate the expected value
        #     for time_passed, _, current, total, src in flushes:
        #         print(f"            [{time_passed}, task, {current}, {total}, 'unknown_via_progress_manager'],")

        self.assertEqual(flushes, [
            # starts right away
            [0.0, task, 1, 100000, 'unknown_via_progress_manager'],
            [99.9, task, 1000, 100000, 'unknown_via_progress_manager'],
            [199.9, task, 2000, 100000, 'unknown_via_progress_manager'],
            [299.9, task, 3000, 100000, 'unknown_via_progress_manager'],
            [399.9, task, 4000, 100000, 'unknown_via_progress_manager'],
            [499.9, task, 5000, 100000, 'unknown_via_progress_manager'],
            [599.9, task, 6000, 100000, 'unknown_via_progress_manager'],
            [699.9, task, 7000, 100000, 'unknown_via_progress_manager'],
            [799.9, task, 8000, 100000, 'unknown_via_progress_manager'],
            [899.9, task, 9000, 100000, 'unknown_via_progress_manager'],
            [999.9, task, 10000, 100000, 'unknown_via_progress_manager'],
            [1099.9, task, 11000, 100000, 'unknown_via_progress_manager'],
            [1199.9, task, 12000, 100000, 'unknown_via_progress_manager'],
            [1299.9, task, 13000, 100000, 'unknown_via_progress_manager'],
            [1399.9, task, 14000, 100000, 'unknown_via_progress_manager'],
            [1499.9, task, 15000, 100000, 'unknown_via_progress_manager'],
            [1599.9, task, 16000, 100000, 'unknown_via_progress_manager'],
            [1699.9, task, 17000, 100000, 'unknown_via_progress_manager'],
            [1799.9, task, 18000, 100000, 'unknown_via_progress_manager'],
            [1899.9, task, 19000, 100000, 'unknown_via_progress_manager'],
            [1999.9, task, 20000, 100000, 'unknown_via_progress_manager'],
            [2099.9, task, 21000, 100000, 'unknown_via_progress_manager'],
            [2199.9, task, 22000, 100000, 'unknown_via_progress_manager'],
            [2299.9, task, 23000, 100000, 'unknown_via_progress_manager'],
            [2399.9, task, 24000, 100000, 'unknown_via_progress_manager'],
            [2499.9, task, 25000, 100000, 'unknown_via_progress_manager'],
            [2599.9, task, 26000, 100000, 'unknown_via_progress_manager'],
            [2699.9, task, 27000, 100000, 'unknown_via_progress_manager'],
            [2799.9, task, 28000, 100000, 'unknown_via_progress_manager'],
            [2899.9, task, 29000, 100000, 'unknown_via_progress_manager'],
            [2999.9, task, 30000, 100000, 'unknown_via_progress_manager'],
            [3099.9, task, 31000, 100000, 'unknown_via_progress_manager'],
            [3199.9, task, 32000, 100000, 'unknown_via_progress_manager'],
            [3299.9, task, 33000, 100000, 'unknown_via_progress_manager'],
            [3399.9, task, 34000, 100000, 'unknown_via_progress_manager'],
            [3499.9, task, 35000, 100000, 'unknown_via_progress_manager'],
            [3599.9, task, 36000, 100000, 'unknown_via_progress_manager'],
            [3699.9, task, 37000, 100000, 'unknown_via_progress_manager'],
            [3799.9, task, 38000, 100000, 'unknown_via_progress_manager'],
            [3899.9, task, 39000, 100000, 'unknown_via_progress_manager'],
            [3999.9, task, 40000, 100000, 'unknown_via_progress_manager'],
            [4099.9, task, 41000, 100000, 'unknown_via_progress_manager'],
            [4199.9, task, 42000, 100000, 'unknown_via_progress_manager'],
            [4299.9, task, 43000, 100000, 'unknown_via_progress_manager'],
            [4399.9, task, 44000, 100000, 'unknown_via_progress_manager'],
            [4499.9, task, 45000, 100000, 'unknown_via_progress_manager'],
            [4599.9, task, 46000, 100000, 'unknown_via_progress_manager'],
            [4699.9, task, 47000, 100000, 'unknown_via_progress_manager'],
            [4799.9, task, 48000, 100000, 'unknown_via_progress_manager'],
            [4899.9, task, 49000, 100000, 'unknown_via_progress_manager'],
            [4999.9, task, 50000, 100000, 'unknown_via_progress_manager'],
            [5099.9, task, 51000, 100000, 'unknown_via_progress_manager'],
            [5199.9, task, 52000, 100000, 'unknown_via_progress_manager'],
            [5299.9, task, 53000, 100000, 'unknown_via_progress_manager'],
            [5399.9, task, 54000, 100000, 'unknown_via_progress_manager'],
            [5499.9, task, 55000, 100000, 'unknown_via_progress_manager'],
            [5599.9, task, 56000, 100000, 'unknown_via_progress_manager'],
            [5699.9, task, 57000, 100000, 'unknown_via_progress_manager'],
            [5799.9, task, 58000, 100000, 'unknown_via_progress_manager'],
            [5899.9, task, 59000, 100000, 'unknown_via_progress_manager'],
            [5999.9, task, 60000, 100000, 'unknown_via_progress_manager'],
            [6099.9, task, 61000, 100000, 'unknown_via_progress_manager'],
            [6199.9, task, 62000, 100000, 'unknown_via_progress_manager'],
            [6299.9, task, 63000, 100000, 'unknown_via_progress_manager'],
            [6399.9, task, 64000, 100000, 'unknown_via_progress_manager'],
            [6499.9, task, 65000, 100000, 'unknown_via_progress_manager'],
            [6599.9, task, 66000, 100000, 'unknown_via_progress_manager'],
            [6699.9, task, 67000, 100000, 'unknown_via_progress_manager'],
            [6799.9, task, 68000, 100000, 'unknown_via_progress_manager'],
            [6899.9, task, 69000, 100000, 'unknown_via_progress_manager'],
            [6999.9, task, 70000, 100000, 'unknown_via_progress_manager'],
            [7099.9, task, 71000, 100000, 'unknown_via_progress_manager'],
            [7199.9, task, 72000, 100000, 'unknown_via_progress_manager'],
            [7299.9, task, 73000, 100000, 'unknown_via_progress_manager'],
            [7399.9, task, 74000, 100000, 'unknown_via_progress_manager'],
            [7499.9, task, 75000, 100000, 'unknown_via_progress_manager'],
            [7599.9, task, 76000, 100000, 'unknown_via_progress_manager'],
            [7699.9, task, 77000, 100000, 'unknown_via_progress_manager'],
            [7799.9, task, 78000, 100000, 'unknown_via_progress_manager'],
            [7899.9, task, 79000, 100000, 'unknown_via_progress_manager'],
            [7999.9, task, 80000, 100000, 'unknown_via_progress_manager'],
            [8099.9, task, 81000, 100000, 'unknown_via_progress_manager'],
            [8199.9, task, 82000, 100000, 'unknown_via_progress_manager'],
            [8299.9, task, 83000, 100000, 'unknown_via_progress_manager'],
            [8399.9, task, 84000, 100000, 'unknown_via_progress_manager'],
            [8499.9, task, 85000, 100000, 'unknown_via_progress_manager'],
            [8599.9, task, 86000, 100000, 'unknown_via_progress_manager'],
            [8699.9, task, 87000, 100000, 'unknown_via_progress_manager'],
            [8799.9, task, 88000, 100000, 'unknown_via_progress_manager'],
            [8899.9, task, 89000, 100000, 'unknown_via_progress_manager'],
            [8999.9, task, 90000, 100000, 'unknown_via_progress_manager'],
            [9099.9, task, 91000, 100000, 'unknown_via_progress_manager'],
            [9199.9, task, 92000, 100000, 'unknown_via_progress_manager'],
            [9299.9, task, 93000, 100000, 'unknown_via_progress_manager'],
            [9399.9, task, 94000, 100000, 'unknown_via_progress_manager'],
            [9499.9, task, 95000, 100000, 'unknown_via_progress_manager'],
            [9599.9, task, 96000, 100000, 'unknown_via_progress_manager'],
            [9699.9, task, 97000, 100000, 'unknown_via_progress_manager'],
            [9799.9, task, 98000, 100000, 'unknown_via_progress_manager'],
            [9899.9, task, 99000, 100000, 'unknown_via_progress_manager'],
            [9999.9, task, 100000, 100000, 'unknown_via_progress_manager'],
            # flushes final update
            [10000.0, task, 100000, 100000, 'unknown_via_progress_manager'],
            # total of 102 updates
        ])
