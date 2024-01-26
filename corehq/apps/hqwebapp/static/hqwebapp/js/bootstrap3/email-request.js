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

        self.resetForm = function () {
            self.$formElement.find("button[type='submit']").button('reset');
            self.$formElement.resetForm();
            self.cancelBtnEnabled(true);
            self.$submitBtn.button('reset');
            self.hasEmailInputError(false);
        };

        function resetErrors() {
            self.hasSubmitError(false);
            self.hasSubjectError(false);
            self.hasEmailInputError(false);
            self.hasOtherEmailInputError(false);
            self.hasRecipientsInputError(false);
        }

        function hqwebappRequestReportBeforeSerialize() {
            self.reportUrl(location.href);
        }

        function hqwebappRequestReportBeforeSubmit() {
            self.isRequestReportSubmitting = true;
        }

        function hqwebappRequestReportSucccess() {
            self.isRequestReportSubmitting = false;
            self.$submitBtn.button('success');
        }

        function hqwebappRequestReportError() {
            self.isRequestReportSubmitting = false;
            self.$submitBtn.button('error');
            self.cancelBtnEnabled(true);
            self.hasSubmitError(true);
        }

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
