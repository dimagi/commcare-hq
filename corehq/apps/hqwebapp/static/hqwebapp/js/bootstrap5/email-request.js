hqDefine('hqwebapp/js/bootstrap5/email-request', [
    "jquery",
    "knockout",
    "es6!hqwebapp/js/bootstrap5_loader",
    "jquery-form/dist/jquery.form.min",
    "hqwebapp/js/bootstrap5/hq.helpers",
], function ($, ko, bootstrap) {
    'use strict';

    var EmailRequest = function (modalId, formId) {
        let self = {};

        self.$element = $(`#${modalId}`);
        self.reportModal = new bootstrap.Modal(self.$element);
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
                self.reportModal.hide();
            } else if (!self.isRequestReportSubmitting) {
                self.$submitBtn.changeButtonState('loading');
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
            self.$formElement.find("button[type='submit']").changeButtonState('reset');
            self.$formElement.resetForm();
            self.cancelBtnEnabled(true);
            self.$submitBtn.changeButtonState('reset');
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
            self.$submitBtn.changeButtonState('success');
        }

        function hqwebappRequestReportError() {
            self.isRequestReportSubmitting = false;
            self.$submitBtn.changeButtonState('error');
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
