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
