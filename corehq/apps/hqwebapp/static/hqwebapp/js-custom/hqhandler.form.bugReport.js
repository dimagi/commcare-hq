$.fn.bootstrapButton = $.fn.button;

$(function () {
    var $hqwebappBugReportModal = $('#modalReportIssue'),
        $hqwebappBugReportForm = $('#hqwebapp-bugReportForm'),
        $hqwebappBugReportCancel = $('#bug-report-cancel'),
        isBugReportSubmitting = false;

    $hqwebappBugReportModal.on('show', function() {
        $hqwebappBugReportForm.find("button[type='submit']").bootstrapButton('reset');
        $hqwebappBugReportForm.resetForm();
        $hqwebappBugReportCancel.bootstrapButton('reset');
    });
    $hqwebappBugReportModal.on('shown', function() {
        $("input#bug-report-subject").focus();
    });

    var $emailAlert = $("#invalid-email-alert");
    var $ccAlert = $("#invalid-cc-alert");
    var $descriptionAlert = $("#empty-issue-alert");
    renderAlerts($ccAlert, $descriptionAlert);

    $hqwebappBugReportForm.submit(function() {
        var isDescriptionEmpty = !$("#bug-report-subject").val() && !$("#bug-report-message").val();
        if (isDescriptionEmpty) {
            $descriptionAlert.show();
        }

        var emailAddress = $(this).find("input[name='email']").val();
        if (emailAddress && !IsValidEmail(emailAddress)){
            $emailAlert.show();
            return false;
        }

        var emailAddresses = $(this).find("input[name='cc']").val();
        emailAddresses = emailAddresses.replace(/ /g, "").split(",");
        for (var index in emailAddresses){
            var email = emailAddresses[index];
            if (email && !IsValidEmail(email)){
                $ccAlert.show();
                return false;
            }
        }
        if (isDescriptionEmpty) {
            return false;
        }
        var $submitButton = $(this).find("button[type='submit']");
        if(!isBugReportSubmitting && $submitButton.text() == $submitButton.data("success-text")) {
            $hqwebappBugReportModal.modal("hide");
        }else if(!isBugReportSubmitting) {
            $submitButton.bootstrapButton('loading');
            $hqwebappBugReportCancel.bootstrapButton('loading');
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

    function renderAlerts($ccAlert, $descriptionAlert) {
        var $alertBoxes = $("#hqwebapp-bugReportForm .alert");

        $alertBoxes.hide();
        
        hideAlert($("#bug-report-cc"), $ccAlert);
        hideAlert($("#bug-report-message"), $descriptionAlert);

        function hideAlert($input, $boxToHide) {
            $input.focus(
                function(){
                    $boxToHide.hide();
                }
            );
        }
    }
    function IsValidEmail(email) {
        var regex = /^([a-zA-Z0-9_.+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
        return regex.test(email);
    }
    function hqwebappBugReportBeforeSerialize($form, options) {
        $form.find("#bug-report-url").val(location.href);
    }

    function hqwebappBugReportBeforeSubmit(arr, $form, options) {
        isBugReportSubmitting = true;
    }

    function hqwebappBugReportSucccess(data) {
        isBugReportSubmitting = false;
        $hqwebappBugReportForm.find("button[type='submit']").bootstrapButton('success').removeClass('btn-primary btn-danger').addClass('btn-success');
    }

    function hqwebappBugReportError(data) {
        isBugReportSubmitting = false;
        $hqwebappBugReportForm.find("button[type='submit']").bootstrapButton('error').removeClass('btn-primary btn-success').addClass('btn-danger');
    }
});
