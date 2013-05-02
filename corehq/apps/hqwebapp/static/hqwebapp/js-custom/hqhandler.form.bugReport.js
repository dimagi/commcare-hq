$.fn.bootstrapButton = $.fn.button;

$(function () {
    var $hqwebappBugReportModal = $('#reportIssueModal'),
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

    $hqwebappBugReportForm.submit(function() {
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