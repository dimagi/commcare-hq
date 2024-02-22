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
        self.hasRecipientsInputError = ko.observable(false);

        self.isRequestReportSubmitting = false;
        self.isReportSent = false;

        self.reportUrl = ko.observable('');

        self.$formElement.submit(() => {
            resetErrors();

            const isSubjectEmpty = !self.subjectText();
            if (isSubjectEmpty) {
                self.hasSubjectError(true);
            }

            if (self.emailInput() && !isValidEmail(self.emailInput())) {
                self.hasEmailInputError(true);
                return false;
            }

            const emailAddresses = self.recipientEmailsText().replace(/ /g, "").split(",");
            for (const email of emailAddresses) {
                if (email && !isValidEmail(email)) {
                    self.hasRecipientsInputError(true);
                    return false;
                }
            }
            if (isSubjectEmpty) {
                return false;
            }

            if (!self.isRequestReportSubmitting && self.isReportSent) {
                self.isReportSent = false;
                self.$element.modal('hide');
            } else if (!self.isRequestReportSubmitting) {
                self.$submitBtn.button('loading');
                self.cancelBtnEnabled(false);
                self.$formElement.ajaxSubmit({
                    type: "POST",
                    url: self.$formElement.attr('action'),
                    beforeSerialize: hqwebappRequestReportBeforeSerialize,
                    beforeSubmit: hqwebappRequestReportBeforeSubmit,
                    success: hqwebappRequestReportSucccess,
                    error: hqwebappRequestReportError,
                });
            }
            return false;
        });

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

        function isValidEmail(email) {
            var regex = /^([a-zA-Z0-9_.+-])+@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            return regex.test(email);
        }

        function resetErrors() {
            self.hasSubmitError(false);
            self.hasSubjectError(false);
            self.hasEmailInputError(false);
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
            self.isReportSent = true;
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
        const issueReportModal = $("#modalReportIssue");
        if (issueReportModal.length) {
            issueReportModal.koApplyBindings(new EmailRequest(
                "modalReportIssue",
                "hqwebapp-bugReportForm"
            ));
        }
        const featureRequestModal = $("#modalSolutionsFeatureRequest");
        if (featureRequestModal.length) {
            featureRequestModal.koApplyBindings(new EmailRequest(
                "modalSolutionsFeatureRequest",
                "hqwebapp-requestReportForm"
            ));
        }
    });
});
