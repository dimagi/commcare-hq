hqDefine('hqwebapp/js/bootstrap5/solutions-feature-request', [
    "jquery",
    "es6!hqwebapp/js/bootstrap5_loader",
    "jquery-form/dist/jquery.form.min",
    "hqwebapp/js/bootstrap5/hq.helpers",
], function ($, bootstrap) {
    'use strict';
    $(function () {
        let self = {};

        self.$requestReportModalElement = $('#modalSolutionsFeatureRequest');
        if (self.$requestReportModalElement.length === 0) {
            // If the modal element is not present on the page, don't continue
            return;
        }

        self.requestReportModal = new bootstrap.Modal(self.$requestReportModalElement);
        self.$hqwebappRequestReportForm = $('#hqwebapp-requestReportForm');
        self.$hqwebappRequestReportSubmit = $('#request-report-submit');
        self.$hqwebappRequestReportCancel = $('#request-report-cancel');
        self.$ccFormGroup = $("#request-report-cc-form-group");
        self.$emailFormGroup = $("#request-report-email-form-group");
        self.$issueSubjectFormGroup = $("#request-report-subject-form-group");
        self.isRequestReportSubmitting = false;

        self.resetForm = function () {
            self.$hqwebappRequestReportForm.find("button[type='submit']").changeButtonState('reset');
            self.$hqwebappRequestReportForm.resetForm();
            self.$hqwebappRequestReportCancel.enableButton();
            self.$hqwebappRequestReportSubmit.changeButtonState('reset');
            self.$ccFormGroup.removeClass('has-error has-feedback');
            self.$ccFormGroup.find(".label-danger").addClass('hide');
            self.$emailFormGroup.removeClass('has-error has-feedback');
            self.$emailFormGroup.find(".label-danger").addClass('hide');
        };

        self.$requestReportModalElement.on('shown.bs.modal', function () {
            $("input#request-report-subject").focus();
        });

        self.$hqwebappRequestReportForm.submit(function (e) {
            e.preventDefault();

            let isDescriptionEmpty = !$("#request-report-subject").val() && !$("#request-report-message").val();
            if (isDescriptionEmpty) {
                self.highlightInvalidField(self.$issueSubjectFormGroup);
            }

            let emailAddress = $(this).find("input[name='email']").val();
            if (emailAddress && !self.isValidEmail(emailAddress)) {
                self.highlightInvalidField(self.$emailFormGroup);
                return false;
            }

            let emailAddresses = $(this).find("input[name='cc']").val();
            emailAddresses = emailAddresses.replace(/ /g, "").split(",");
            for (let index in emailAddresses) {
                let email = emailAddresses[index];
                if (email && !self.isValidEmail(email)) {
                    self.highlightInvalidField(self.$ccFormGroup);
                    return false;
                }
            }
            if (isDescriptionEmpty) {
                return false;
            }

            if (!self.isRequestReportSubmitting && self.$hqwebappRequestReportSubmit.text() ===
                    self.$hqwebappRequestReportSubmit.data("success-text")) {
                self.requestReportModal.hide();
            } else if (!self.isRequestReportSubmitting) {
                self.$hqwebappRequestReportCancel.disableButtonNoSpinner();
                self.$hqwebappRequestReportSubmit.changeButtonState('loading');
                $(this).ajaxSubmit({
                    type: "POST",
                    url: $(this).attr('action'),
                    beforeSerialize: self.hqwebappRequestReportBeforeSerialize,
                    beforeSubmit: self.hqwebappRequestReportBeforeSubmit,
                    success: self.hqwebappRequestReportSuccess,
                    error: self.hqwebappRequestReportError,
                });
            }
            return false;
        });

        self.isValidEmail = function (email) {
            let regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            return regex.test(email);
        };

        self.hqwebappRequestReportBeforeSerialize = function ($form) {
            $form.find("#request-report-url").val(location.href);
        };

        self.hqwebappRequestReportBeforeSubmit = function () {
            self.isRequestReportSubmitting = true;
        };

        self.hqwebappRequestReportSuccess = function () {
            self.isRequestReportSubmitting = false;
            self.$requestReportModalElement.one('hidden.bs.modal', function () {
                self.resetForm();
            });
            self.$hqwebappRequestReportForm.find("button[type='submit']")
                .changeButtonState('success')
                .removeClass('btn-danger').addClass('btn-primary');
        };

        self.hqwebappRequestReportError = function () {
            self.isRequestReportSubmitting = false;
            self.$hqwebappRequestReportForm.find("button[type='submit']").changeButtonState('error')
                .removeClass('btn-primary').addClass('btn-danger');
            self.$hqwebappRequestReportCancel.enableButton();
        };

        self.highlightInvalidField = function ($element) {
            $element.addClass('has-error has-feedback');
            $element.find(".label-danger").removeClass('hide');
            $element.find("input").focus(function () {
                $element.removeClass("has-error has-feedback");
                $element.find(".label-danger").addClass('hide');
            });
        };
    });
});
