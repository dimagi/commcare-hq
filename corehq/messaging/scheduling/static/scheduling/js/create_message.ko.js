hqDefine("scheduling/js/create_message.ko", function() {
    var CreateMessageViewModel = function (initial_values) {
        var self = this;

        self.schedule_name = ko.observable(initial_values.schedule_name);

        self.is_trial_project = initial_values.is_trial_project;
        self.displayed_email_trial_message = false;
        self.translate = ko.observable(initial_values.translate);

        self.init = function () {};
    };

    $(function () {
        var cmvm = new CreateMessageViewModel(hqImport("hqwebapp/js/initial_page_data").get("current_values"));
        $('#create-message-form').koApplyBindings(cmvm);
        cmvm.init();
    });
});
