hqDefine('hqwebapp/js/bootstrap5/hq-bug-report', [
    "jquery",
    "hqwebapp/js/bootstrap5_loader",
    "jquery-form/dist/jquery.form.min",
    "hqwebapp/js/bootstrap5/hq.helpers",
], function ($, bootstrap) {
    'use strict';
    $(function () {
        let self = {};

        self.$bugReportModalElement = $('#modalReportIssue');
        if (self.$bugReportModalElement.length === 0) {
            // If the modal element is not present on the page, don't continue
            return;
        }

        self.bugReportModal = new bootstrap.Modal(self.$bugReportModalElement);
        self.$hqwebappBugReportForm = $('#hqwebapp-bugReportForm');
        self.$hqwebappBugReportSubmit = $('#bug-report-submit');
        self.$hqwebappBugReportCancel = $('#bug-report-cancel');
        self.$ccFormGroup = $("#bug-report-cc-form-group");
        self.$emailFormGroup = $("#bug-report-email-form-group");
        self.$issueSubjectFormGroup = $("#bug-report-subject-form-group");
        self.isBugReportSubmitting = false;

        self.resetForm = function () {
            self.$hqwebappBugReportForm.find("button[type='submit']").changeButtonState('reset');
            self.$hqwebappBugReportForm.resetForm();
            self.$hqwebappBugReportCancel.enableButton();
            self.$hqwebappBugReportSubmit.changeButtonState('reset');
            self.$ccFormGroup.removeClass('has-error has-feedback');
            self.$ccFormGroup.find(".label-danger").addClass('hide');
            self.$emailFormGroup.removeClass('has-error has-feedback');
            self.$emailFormGroup.find(".label-danger").addClass('hide');
        };

        self.$bugReportModalElement.on('shown.bs.modal', function () {
            $("input#bug-report-subject").focus();
        });

        self.$hqwebappBugReportForm.submit(function (e) {
            e.preventDefault();

            let isDescriptionEmpty = !$("#bug-report-subject").val() && !$("#bug-report-message").val();
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

            if (!self.isBugReportSubmitting && self.$hqwebappBugReportSubmit.text() ===
                    self.$hqwebappBugReportSubmit.data("success-text")) {
                self.bugReportModal.hide();
            } else if (!self.isBugReportSubmitting) {
                self.$hqwebappBugReportCancel.disableButtonNoSpinner();
                self.$hqwebappBugReportSubmit.changeButtonState('loading');
                $(this).ajaxSubmit({
                    type: "POST",
                    url: $(this).attr('action'),
                    beforeSerialize: self.hqwebappBugReportBeforeSerialize,
                    beforeSubmit: self.hqwebappBugReportBeforeSubmit,
                    success: self.hqwebappBugReportSuccess,
                    error: self.hqwebappBugReportError,
                });
            }
            return false;
        });

        self.isValidEmail = function (email) {
            let regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            return regex.test(email);
        };

        self.hqwebappBugReportBeforeSerialize = function ($form) {
            $form.find("#bug-report-url").val(location.href);
        };

        self.hqwebappBugReportBeforeSubmit = function () {
            self.isBugReportSubmitting = true;
        };

        self.hqwebappBugReportSuccess = function () {
            self.isBugReportSubmitting = false;
            self.$bugReportModalElement.one('hidden.bs.modal', function () {
                self.resetForm();
            });
            self.$hqwebappBugReportForm.find("button[type='submit']")
                .changeButtonState('success')
                .removeClass('btn-danger').addClass('btn-primary');
        };

        self.hqwebappBugReportError = function () {
            self.isBugReportSubmitting = false;
            self.$hqwebappBugReportForm.find("button[type='submit']").changeButtonState('error')
                .removeClass('btn-primary').addClass('btn-danger');
            self.$hqwebappBugReportCancel.enableButton();
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
