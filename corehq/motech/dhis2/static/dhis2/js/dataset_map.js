hqDefine("dhis2/js/dataset_map", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap5/crud_paginated_list_init",
    "hqwebapp/js/bootstrap5/widgets",
    "commcarehq",
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var $sendNowResult = $('#send-now-result'),
            $remoteLogsLink = $('#remote-logs');
        $remoteLogsLink.addClass("d-none");

        var handleSuccess = function (response) {
            $sendNowResult.removeClass("d-none text-danger text-success");
            if (response.success) {
                $sendNowResult.addClass("text-success");
            } else {
                $sendNowResult.addClass("text-danger");
            }
            $sendNowResult.text(gettext('DHIS2 response: ') + response.text);
            if (response.log_url) {
                $remoteLogsLink.attr('href', response.log_url);
                $remoteLogsLink.removeClass("d-none");
            }
        };

        var handleFailure = function (resp) {
            $sendNowResult
                .removeClass("d-none text-success")
                .addClass("text-danger");
            $sendNowResult.text(
                gettext('CommCare HQ was unable to send the DataSet: ')
                + (resp.responseJSON ? resp.responseJSON['error'] : resp.statusText)
            );
            if (resp.responseJSON) {
                $remoteLogsLink.attr('href', resp.responseJSON['log_url']);
                $remoteLogsLink.removeClass("d-none");
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
