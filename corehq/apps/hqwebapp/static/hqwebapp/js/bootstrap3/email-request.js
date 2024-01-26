hqDefine('hqwebapp/js/bootstrap3/email-request', [
    "jquery",
    "knockout",
    "jquery-form/dist/jquery.form.min",
    "hqwebapp/js/bootstrap3/hq.helpers",
], function ($, ko) {

    var EmailRequest = function (modalId, formId) {
        let self = {};

        self.$element = $(`#${modalId}`);
        self.$formElement = $(`#${formId}`);
        self.$submitBtn = self.$formElement.find("button[type='submit']");

        self.subjectText = ko.observable('');
        self.descriptionText = ko.observable('');
        self.emailInput = ko.observable('');
        self.recipientEmailsText = ko.observable('');

        self.subjectHasFocus = ko.observable(false);
        self.cancelBtnEnabled = ko.observable(true);

        self.hasSubmitError = ko.observable(false);
        self.hasSubjectError = ko.observable(false);
        self.hasEmailInputError = ko.observable(false);
        self.hasOtherEmailInputError = ko.observable(false);
        self.hasRecipientsInputError = ko.observable(false);

        self.isRequestReportSubmitting = false;

        self.reportUrl = ko.observable('');
        self.openModal = function () {
            self.subjectHasFocus(true);
        };

        return self;
    };

    $(function () {
        $("#modalReportIssue").koApplyBindings(new EmailRequest(
            "modalReportIssue",
            "hqwebapp-bugReportForm"
        ));
        $("#modalSolutionsFeatureRequest").koApplyBindings(new EmailRequest(
            "modalSolutionsFeatureRequest",
            "hqwebapp-requestReportForm"
        ));
    });
});
