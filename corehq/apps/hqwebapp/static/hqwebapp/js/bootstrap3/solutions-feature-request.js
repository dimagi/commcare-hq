hqDefine('hqwebapp/js/bootstrap3/solutions-feature-request', [
    "jquery", "jquery-form/dist/jquery.form.min", "hqwebapp/js/bootstrap3/hq.helpers",
], function ($) {
    $(function () {
        var $hqwebappRequestReportModal = $('#modalSolutionsFeatureRequest'),
            $hqwebappRequestReportForm = $('#hqwebapp-requestReportForm'),
            $hqwebappRequestReportSubmit = $('#request-report-submit'),
            $hqwebappRequestReportCancel = $('#request-report-cancel'),
            $ccFormGroup = $("#request-report-cc-form-group"),
            $emailFormGroup = $("#request-report-email-form-group"),
            $issueSubjectFormGroup = $("#request-report-subject-form-group"),
            isRequestReportSubmitting = false;

        var resetForm = function () {
            $hqwebappRequestReportForm.find("button[type='submit']").button('reset');
            $hqwebappRequestReportForm.resetForm();
            $hqwebappRequestReportCancel.enableButton();
            $hqwebappRequestReportSubmit.button('reset');
            $ccFormGroup.removeClass('has-error has-feedback');
            $ccFormGroup.find(".label-danger").addClass('hide');
            $emailFormGroup.removeClass('has-error has-feedback');
            $emailFormGroup.find(".label-danger").addClass('hide');
        };

        $hqwebappRequestReportModal.on('shown.bs.modal', function () {
            $("input#request-report-subject").focus();
        });

        $hqwebappRequestReportForm.submit(function () {
            var isDescriptionEmpty = !$("#request-report-subject").val() && !$("#request-report-message").val();
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

            if (!isRequestReportSubmitting && $hqwebappRequestReportSubmit.text() === $hqwebappRequestReportSubmit.data("success-text")) {
                $hqwebappRequestReportModal.modal("hide");
            } else if (!isRequestReportSubmitting) {
                $hqwebappRequestReportCancel.disableButtonNoSpinner();
                $hqwebappRequestReportSubmit.button('loading');
                $(this).ajaxSubmit({
                    type: "POST",
                    url: $(this).attr('action'),
                    beforeSerialize: hqwebappRequestReportBeforeSerialize,
                    beforeSubmit: hqwebappRequestReportBeforeSubmit,
                    success: hqwebappRequestReportSucccess,
                    error: hqwebappRequestReportError,
                });
            }
            return false;
        });

        function IsValidEmail(email) {
            var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            return regex.test(email);
        }

        function hqwebappRequestReportBeforeSerialize($form) {
            $form.find("#request-report-url").val(location.href);
        }

        function hqwebappRequestReportBeforeSubmit() {
            isRequestReportSubmitting = true;
        }

        function hqwebappRequestReportSucccess() {
            isRequestReportSubmitting = false;
            $hqwebappRequestReportForm.find("button[type='submit']").button('success').removeClass('btn-danger').addClass('btn-primary');
            $hqwebappRequestReportModal.one('hidden.bs.modal', function () {
                resetForm();
            });
        }

        function hqwebappRequestReportError() {
            isRequestReportSubmitting = false;
            $hqwebappRequestReportForm.find("button[type='submit']").button('error').removeClass('btn-primary').addClass('btn-danger');
            $hqwebappRequestReportCancel.enableButton();
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
