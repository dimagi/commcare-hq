var RemindersListModel = function (reminders, progressUrl) {
    'use strict';
    var self = this;
    self.reminders = reminders;
    self.progressUrl = progressUrl;

    self.activeReminders = ko.observableArray();
    self.inactiveReminders = ko.observableArray();

    self.init = function () {
        var active = [],
            inactive = [];
        _(self.reminders).each(function (reminder) {
            if (reminder.isActive) {
                active.push(new Reminder(reminder, self));
            } else {
                inactive.push(new Reminder(reminder, self));
            }
        });
        self.activeReminders(active);
        self.inactiveReminders(inactive);
    };

    self.deactivateReminder = function (reminder) {
        var trans = self.utils.transferReminder(
            self.activeReminders(),
            self.inactiveReminders(),
            reminder
        );
        self.activeReminders(trans.from);
        self.inactiveReminders(trans.to);
    };

    self.activateReminder = function (reminder) {
        var trans = self.utils.transferReminder(
            self.inactiveReminders(),
            self.activeReminders(),
            reminder
        );
        self.inactiveReminders(trans.from);
        self.activeReminders(trans.to);
    };

    self.removeReminder = function (id) {
        self.activeReminders.remove(function(item) { return item.id === id; });
        self.inactiveReminders.remove(function(item) { return item.id === id; });
    }

    self.utils = {
        transferReminder: function (from, to, rem) {
            var to_list = _.union([rem], to);
            var from_list = _(from).filter(function (r) {
                return r.id !== rem.id;
            });
            return {
                from: from_list,
                to: to_list
            }
        }
    }
};

var Reminder = function (o, parentModel) {
    'use strict';
    var self = this;

    self.reminderList = parentModel;

    self.id = ko.observable(o.id);
    self.name = ko.observable(o.name);
    self.caseType = ko.observable(o.caseType);
    self.url = ko.observable(o.url);
    self.progressBar = new RuleProgressBar(o.id, parentModel.progressUrl);

    self.activate = function (_, event) {
        self.processReminder('activate', event.target);
    };

    self.deactivate = function (_, event) {
        self.processReminder('deactivate', event.target);
    };

    self.del = function(_, event) {
        self.processReminder('delete', event.target);
    };

    self.processReminder = function (method, target_button) {
        $(target_button).button('loading');
        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: {
                action: method,
                reminderId: self.id
            },
            error: function (data) {
                $(target_button).button('error');
            },
            success: function (data) {
                if (data.success) {
                    if(method == 'delete') {
                        self.reminderList.removeReminder(self.id);
                    } else {
                        self.reminderList[method + 'Reminder'](self);
                    }
                } else {
                    if(data.locked) {
                        $(target_button).button('locked');
                    } else {
                        $(target_button).button('error');
                    }
                }
            }
        });
    }
};


