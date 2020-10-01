/*
 * Executes the queue in a FIFO action. If name is supplied, will execute the first
 * task for that name.
 */
hqDefine("cloudcare/js/form_entry/task_queue", function () {
    var TaskQueue = function () {
        var self = {};

        self.queue = [];

        self.execute = function (name) {
console.log("Executing any " + name + " tasks");
            var task,
                idx;
            if (name) {
                idx = _.indexOf(_.pluck(self.queue, 'name'), name);
                if (idx === -1) {
                    return;
                }
                task = self.queue.splice(idx, 1)[0];
            } else {
                task = self.queue.shift();
            }
            if (!task) {
                return;
            }
            task.fn.apply(task.thisArg, task.parameters);
        };

        self.addTask = function (name, fn, parameters, thisArg) {
console.log("Added task " + name);
            var task = {
                name: name,
                fn: fn,
                parameters: parameters,
                thisArg: thisArg,
            };
            self.queue.push(task);
            return task;
        };

        // jls
        //self.hasTask = function (name, parameters) {

        self.clearTasks = function (name, args, max) {
console.log("Clearing tasks of type " + name + ", at most " + max);
            args = args || {};
            var cleared = 0, idx, matchingTask;
            if (name || !_.isEmpty(args)) {
                while ((!max || cleared < max) && (matchingTask = _.find(self.queue, function (t) {
                    var match = !name || name === t.name;
                    match = match && _.isMatch(t.parameters, args);
                    return match;
                }))) {
                    idx = _.indexOf(self.queue, matchingTask);
                    self.queue.splice(idx, 1);
                    cleared++;
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
