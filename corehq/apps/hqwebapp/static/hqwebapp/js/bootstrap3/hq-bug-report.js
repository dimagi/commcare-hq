hqDefine('hqwebapp/js/bootstrap3/hq-bug-report', [
    "jquery", "jquery-form/dist/jquery.form.min", "hqwebapp/js/bootstrap3/hq.helpers",
], function ($) {
    $(function () {
        var $hqwebappBugReportModal = $('#modalReportIssue'),
            $hqwebappBugReportForm = $('#hqwebapp-bugReportForm'),
            $hqwebappBugReportSubmit = $('#bug-report-submit'),
            $hqwebappBugReportCancel = $('#bug-report-cancel'),
            $ccFormGroup = $("#bug-report-cc-form-group"),
            $emailFormGroup = $("#bug-report-email-form-group"),
            $issueSubjectFormGroup = $("#bug-report-subject-form-group"),
            isBugReportSubmitting = false;

        var resetForm = function () {
            $hqwebappBugReportForm.find("button[type='submit']").button('reset');
            $hqwebappBugReportForm.resetForm();
            $hqwebappBugReportCancel.enableButton();
            $hqwebappBugReportSubmit.button('reset');
            $ccFormGroup.removeClass('has-error has-feedback');
            $ccFormGroup.find(".label-danger").addClass('hide');
            $emailFormGroup.removeClass('has-error has-feedback');
            $emailFormGroup.find(".label-danger").addClass('hide');
        };

        $hqwebappBugReportModal.on('shown.bs.modal', function () {
            $("input#bug-report-subject").focus();
        });

        $hqwebappBugReportForm.submit(function () {
            var isDescriptionEmpty = !$("#bug-report-subject").val() && !$("#bug-report-message").val();
            if (isDescriptionEmpty) {
                highlightInvalidField($issueSubjectFormGroup);
            }

            var emailAddress = $(this).find("input[name='email']").val();
            if (emailAddress && !IsValidEmail(emailAddress)) {
                highlightInvalidField($emailFormGroup);
                return false;
            }

            var emailAddresses = $(this).find("input[name='cc']").val();
            emailAddresses = emailAddresses.replace(/ /g, "").split(",");
            for (var index in emailAddresses) {
                var email = emailAddresses[index];
                if (email && !IsValidEmail(email)) {
                    highlightInvalidField($ccFormGroup);
                    return false;
                }
            }
            if (isDescriptionEmpty) {
                return false;
            }

            if (!isBugReportSubmitting && $hqwebappBugReportSubmit.text() === $hqwebappBugReportSubmit.data("success-text")) {
                $hqwebappBugReportModal.modal("hide");
            } else if (!isBugReportSubmitting) {
                $hqwebappBugReportCancel.disableButtonNoSpinner();
                $hqwebappBugReportSubmit.button('loading');
                $(this).ajaxSubmit({
                    type: "POST",
                    url: $(this).attr('action'),
                    beforeSerialize: hqwebappBugReportBeforeSerialize,
                    beforeSubmit: hqwebappBugReportBeforeSubmit,
                    success: hqwebappBugReportSucccess,
                    error: hqwebappBugReportError,
                });
            }
            return false;
        });

        function IsValidEmail(email) {
            var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            return regex.test(email);
        }

        function hqwebappBugReportBeforeSerialize($form) {
            $form.find("#bug-report-url").val(location.href);
        }

        function hqwebappBugReportBeforeSubmit() {
            isBugReportSubmitting = true;
        }

        function hqwebappBugReportSucccess() {
            isBugReportSubmitting = false;
            $hqwebappBugReportForm.find("button[type='submit']").button('success').removeClass('btn-danger').addClass('btn-primary');
            $hqwebappBugReportModal.one('hidden.bs.modal', function () {
                resetForm();
            });
        }

        function hqwebappBugReportError() {
            isBugReportSubmitting = false;
            $hqwebappBugReportForm.find("button[type='submit']").button('error').removeClass('btn-primary').addClass('btn-danger');
            $hqwebappBugReportCancel.enableButton();
        }

        function highlightInvalidField($element) {
            $element.addClass('has-error has-feedback');
            $element.find(".label-danger").removeClass('hide');
            $element.find("input").focus(function () {
                $element.removeClass("has-error has-feedback");
                $element.find(".label-danger").addClass('hide');
            });
        }
    });
});
