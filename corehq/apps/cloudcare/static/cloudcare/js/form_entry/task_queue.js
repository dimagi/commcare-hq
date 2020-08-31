/*
 * Executes the queue in a FIFO action. If name is supplied, will execute the first
 * task for that name.
 */
hqDefine("cloudcare/js/form_entry/task_queue", function () {
    var TaskQueue = function () {
        var self = {};

        self.queue = [];

        self.execute = function (name) {
            var task,
                idx;
            if (name) {
                idx = _.indexOf(_.pluck(this.queue, 'name'), name);
                if (idx === -1) {
                    return;
                }
                task = this.queue.splice(idx, 1)[0];
            } else {
                task = this.queue.shift();
            }
            if (!task) {
                return;
            }
            task.fn.apply(task.thisArg, task.parameters);
        };

        self.addTask = function (name, fn, parameters, thisArg) {
            var task = {
                name: name,
                fn: fn,
                parameters: parameters,
                thisArg: thisArg,
            };
            this.queue.push(task);
            return task;
        };

        self.clearTasks = function (name) {
            var idx;
            if (name) {
                idx = _.indexOf(_.pluck(this.queue, 'name'), name);
                while (idx !== -1) {
                    this.queue.splice(idx, 1);
                    idx = _.indexOf(_.pluck(this.queue, 'name'), name);
                }
            } else {
                this.queue = [];
            }
        };

        return self;
    };

    return {
        TaskQueue: TaskQueue,
    };
});
