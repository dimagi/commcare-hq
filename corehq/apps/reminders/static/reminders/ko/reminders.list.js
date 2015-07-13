var RemindersListModel = function (reminders, progressUrl) {
    'use strict';
    var self = this;
    self.reminders = ko.observableArray();
    self.progress_bar_group = new RuleProgressBarGroup(progressUrl);

    self.init = function () {
        _(reminders).each(function (reminder) {
            self.reminders.push(new Reminder(reminder, self));
        });
    };

    self.removeReminder = function (id) {
        self.reminders.remove(function(item) { return item.id() === id; });
        var dt = $("#reminder-list-table").dataTable();
        var row = dt.$("#" + id)[0];
        dt.fnDeleteRow(row);
    };
};

var Reminder = function (o, parentModel) {
    'use strict';
    var self = this;

    self.reminderList = parentModel;

    self.id = ko.observable(o.id);
    self.name = ko.observable(o.name);
    self.caseType = ko.observable(o.caseType);
    self.url = ko.observable(o.url);
    self.progressBar = new RuleProgressBar(o.id, parentModel.progress_bar_group);
    self.active = ko.observable(o.isActive);

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
                    $(target_button).button('success');
                    if(method === 'delete') {
                        self.reminderList.removeReminder(self.id());
                    } else if (method === 'activate') {
                        self.active(true);
                    } else if (method === 'deactivate') {
                        self.active(false);
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
    };
};


