hqDefine("scheduling/js/create_message.ko", function() {
    var CreateMessageViewModel = function (initial_values) {
        var self = this;

        self.schedule_name = ko.observable(initial_values.schedule_name);
        self.message_recipients = new MessagingSelect2Handler(initial_values.recipients);
        self.message_recipients.init();

        self.is_trial_project = initial_values.is_trial_project;
        self.displayed_email_trial_message = false;
        self.translate = ko.observable(initial_values.translate);

        self.init = function () {
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
        $('#create-message-form').koApplyBindings(cmvm);
        cmvm.init();
    });
});
