hqDefine("dhis2/js/dataset_map", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/crud_paginated_list_init",
    "hqwebapp/js/bootstrap3/widgets",
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var $sendNowResult = $('#send-now-result'),
            $remoteLogsLink = $('#remote-logs');
        $remoteLogsLink.hide();

        var handleSuccess = function (response) {
            $sendNowResult.removeClass("hide text-danger text-success");
            if (response.success) {
                $sendNowResult.addClass("text-success");
            } else {
                $sendNowResult.addClass("text-danger");
            }
            $sendNowResult.text(gettext('DHIS2 response: ') + response.text);
            if (response.log_url) {
                $remoteLogsLink.attr('href', response.log_url);
                $remoteLogsLink.show();
            }
        };

        var handleFailure = function (resp) {
            $sendNowResult
                .removeClass("hide text-success")
                .addClass("text-danger");
            $sendNowResult.text(
                gettext('CommCare HQ was unable to send the DataSet: ')
                + (resp.responseJSON ? resp.responseJSON['error'] : resp.statusText)
            );
            if (resp.responseJSON) {
                $remoteLogsLink.attr('href', resp.responseJSON['log_url']);
                $remoteLogsLink.show();
            }
        };

        sendNow = function (dataSetMapId) {
            $.post({
                url: initialPageData.reverse("send_dataset_now", dataSetMapId),
                success: handleSuccess,
                error: handleFailure,
            });
        };
    });
});
