var HQTimezoneHandler = function (o) {
    var self = this;
    self.override_tz = ko.observable(false);
    self.form_is_ready = ko.observable(false);

    self.updateForm = function(data, event) {
        self.form_is_ready(true);
    };
};