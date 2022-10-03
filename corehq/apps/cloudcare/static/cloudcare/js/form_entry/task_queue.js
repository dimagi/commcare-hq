'use strict';
/*
 * Executes the queue in a FIFO action. When a task is added, it will be immediately
 * executed if the queue was previously empty.
 *
 * All task functions are expected to return a promise.
 */
hqDefine("cloudcare/js/form_entry/task_queue", [
    'underscore',
], function (
    _
) {
    var TaskQueue = function () {
        var self = {};

        self.queue = [];
        self.inProgress = undefined;

        self.execute = function () {
            var task;
            task = self.queue.shift();
            if (!task) {
                self.inProgress = undefined;
                return;
            }
            self.inProgress = task.fn.apply(task.thisArg, task.parameters);
            self.inProgress.always(function () {
                self.execute();
            });
        };

        self.addTask = function (name, fn, parameters, thisArg) {
            var task = {
                name: name,
                fn: fn,
                parameters: parameters,
                thisArg: thisArg,
            };
            self.queue.push(task);
            if (!self.inProgress) {
                self.execute();
            }
            return task;
        };

        self.clearTasks = function (name) {
            var idx;
            if (name) {
                idx = _.indexOf(_.pluck(self.queue, 'name'), name);
                while (idx !== -1) {
                    self.queue.splice(idx, 1);
                    idx = _.indexOf(_.pluck(self.queue, 'name'), name);
                }
            } else {
                self.queue = [];
            }
        };

        return self;
    };

    return {
        TaskQueue: TaskQueue,
    };
});
