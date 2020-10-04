/*
 * Executes the queue in a FIFO action.
 */
hqDefine("cloudcare/js/form_entry/task_queue", function () {
    var TaskQueue = function () {
        var self = {};

        self.queue = [];
        self.inProgress = undefined;

        self.execute = function () {
            var task,
                idx;
            task = self.queue.shift();
            if (!task) {
                self.inProgress = undefined;
                return;
            }
            self.inProgress = task.fn.apply(task.thisArg, task.parameters);
            if (self.inProgress) {
                self.inProgress.done(function () {
                    self.execute();
                });
            }
        };

        self.addTask = function (fn, parameters, thisArg) {
            var task = {
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

        return self;
    };

    return {
        TaskQueue: TaskQueue,
    };
});
