$.fn.bootstrapButton = $.fn.button;

$(function () {
    var $hqwebappBugReportModal = $('#modalReportIssue'),
        $hqwebappBugReportForm = $('#hqwebapp-bugReportForm'),
        $hqwebappBugReportCancel = $('#bug-report-cancel'),
        $ccFormGroup = $("#bug-report-cc-form-group"),
        isBugReportSubmitting = false;

    $hqwebappBugReportModal.on('show.bs.modal', function() {
        $hqwebappBugReportForm.find("button[type='submit']").bootstrapButton('reset');
        $hqwebappBugReportForm.resetForm();
        $hqwebappBugReportCancel.bootstrapButton('reset');
        $ccFormGroup.removeClass('has-error has-feedback');
        $ccFormGroup.find(".label-danger").addClass('hide');
    });
    $hqwebappBugReportModal.on('shown.bs.modal', function() {
        $("input#bug-report-subject").focus();
    });

    $hqwebappBugReportForm.submit(function() {
        var emailAddresses = $(this).find("input[name='cc']").val();
        emailAddresses = emailAddresses.replace(/ /g, "").split(",");
        for (var index in emailAddresses){
            var email = emailAddresses[index];
            if (email && !IsValidEmail(email)){
                $ccFormGroup.addClass('has-error has-feedback');
                $ccFormGroup.find(".label-danger").removeClass('hide');
                return false;
            }
        }
        var $submitButton = $(this).find("button[type='submit']");
        if(!isBugReportSubmitting && $submitButton.text() == $submitButton.data("complete-text")) {
            $hqwebappBugReportModal.modal("hide");
        }else if(!isBugReportSubmitting) {
            $submitButton.bootstrapButton('loading');
            $hqwebappBugReportCancel.bootstrapButton('loading');
            $(this).ajaxSubmit({
                type: "POST",
                url: $(this).attr('action'),
                beforeSerialize: hqwebappBugReportBeforeSerialize,
                beforeSubmit: hqwebappBugReportBeforeSubmit,
                success: hqwebappBugReportSucccess
            });
        }
        return false;
    });

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
        $hqwebappBugReportForm.find("button[type='submit']").bootstrapButton('complete');
    }

});
