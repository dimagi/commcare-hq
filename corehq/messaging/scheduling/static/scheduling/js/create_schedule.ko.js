hqDefine("scheduling/js/create_schedule.ko", function() {
    var CreateMessageViewModel = function (initial_values) {
        var self = this;

        self.schedule_name = ko.observable(initial_values.schedule_name);
        self.send_frequency = ko.observable(initial_values.send_frequency);
        self.start_date = ko.observable(initial_values.start_date);
        self.stop_type = ko.observable(initial_values.stop_type);
        self.occurrences = ko.observable(initial_values.occurrences);
        self.message_recipients = new MessagingSelect2Handler(initial_values.recipients);
        self.message_recipients.init();

        self.is_trial_project = initial_values.is_trial_project;
        self.displayed_email_trial_message = false;
        self.translate = ko.observable(initial_values.translate);

        self.showTimeInput = ko.computed(function() {
            return self.send_frequency() != 'immediately';
        });

        self.showStartDateInput = ko.computed(function() {
            return self.send_frequency() != 'immediately';
        });

        self.showStopInput = ko.computed(function() {
            return self.send_frequency() != 'immediately';
        });

        self.computedEndDate = ko.computed(function() {
            if(self.stop_type() != 'never') {
                var start_date_milliseconds = Date.parse(self.start_date());
                var occurrences = parseInt(self.occurrences());

                if(!isNaN(start_date_milliseconds) && !isNaN(occurrences)) {
                    if(self.send_frequency() == 'daily') {
                        var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
                        var end_date = new Date(start_date_milliseconds + ((occurrences - 1) * milliseconds_in_a_day));
                        return end_date.toJSON().substr(0, 10);
                    }
                }
            }
            return '';
        });

        self.initDatePicker = function(element) {
            element.datepicker({dateFormat : "yy-mm-dd"});
        };

        self.initTimePicker = function(element) {
            element.timepicker({
                showMeridian: false,
                showSeconds: false,
                defaultTime: element.val() || false,
            });
        };

        self.init = function () {
            self.initDatePicker($("#id_start_date"));
            self.initTimePicker($("#id_send_time"));
        };
    };

    var BaseSelect2Handler = hqImport("hqwebapp/js/select2_handler").BaseSelect2Handler,
        MessagingSelect2Handler = function (recipients) {
            BaseSelect2Handler.call(this, {
                fieldName: "recipients",
                multiple: true,
            });
            var self = this;
        
            self.getHandlerSlug = function () {
                return 'messaging_recipients';
            };
        
            self.getInitialData = function () {
                return recipients;
            };
        };
    
    MessagingSelect2Handler.prototype = Object.create(MessagingSelect2Handler.prototype);
    MessagingSelect2Handler.prototype.constructor = MessagingSelect2Handler;

    $(function () {
        var cmvm = new CreateMessageViewModel(hqImport("hqwebapp/js/initial_page_data").get("current_values"));
        $('#create-schedule-form').koApplyBindings(cmvm);
        cmvm.init();
    });
});
