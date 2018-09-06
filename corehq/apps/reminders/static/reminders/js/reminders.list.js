/* globals ruleProgressBarGroup, ruleProgressBar */
hqDefine("reminders/js/reminders.list", function () {
    var remindersListModel = function (reminders, progressUrl) {
        'use strict';
        var self = {};
        self.reminders = ko.observableArray();
        self.progressBarGroup = ruleProgressBarGroup(progressUrl);

        self.init = function () {
            _(reminders).each(function (reminderObj) {
                self.reminders.push(reminder(reminderObj, self));
            });
        };

        self.removeReminder = function (id) {
            self.reminders.remove(function (item) { return item.id() === id; });
            var dt = $("#reminder-list-table").dataTable();
            var row = dt.$("#" + id)[0];
            dt.fnDeleteRow(row);
        };
        return self;
    };

    var reminder = function (o, parentModel) {
        'use strict';
        var self = {};

        self.reminderList = parentModel;

        self.id = ko.observable(o.id);
        self.name = ko.observable(o.name);
        self.caseType = ko.observable(o.caseType);
        self.url = ko.observable(o.url);
        self.progressBar = ruleProgressBar(o.id, parentModel.progressBarGroup);
        self.active = ko.observable(o.isActive);

        self.activate = function (_, event) {
            self.processReminder('activate', event.target);
        };

        self.deactivate = function (_, event) {
            self.processReminder('deactivate', event.target);
        };

        self.del = function (_, event) {
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
                    reminderId: self.id,
                },
                error: function (data) {
                    $(target_button).button('error');
                },
                success: function (data) {
                    if (data.success) {
                        $(target_button).button('success');
                        if (method === 'delete') {
                            self.reminderList.removeReminder(self.id());
                        } else if (method === 'activate') {
                            self.active(true);
                        } else if (method === 'deactivate') {
                            self.active(false);
                        }
                    } else {
                        if (data.locked) {
                            $(target_button).button('locked');
                        } else {
                            $(target_button).button('error');
                        }
                    }
                },
            });
        };

        return self;
    };

    $(function () {
        var remindersList = remindersListModel(hqImport("hqwebapp/js/initial_page_data").get('reminders'),
            hqImport("hqwebapp/js/initial_page_data").reverse("reminder_rule_progress"));
        $('#reminders-list').koApplyBindings(remindersList);
        remindersList.init();

        $("#reminder-list-table").dataTable({
            "paginateType": "bootstrap",
            "lengthChange": false,
            "filter": true,
            "oLanguage": {"emptyTable": gettext('There are no reminders to display.'), "infoEmpty": ""},
            "sort": true,
            "sorting": [[0, "asc"]],
            "displayLength": 5,
        });
    });
});
