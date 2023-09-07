hqDefine("data_interfaces/js/manage_case_groups", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/crud_paginated_list_init',
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var bulkUploadId = initialPageData.get("bulk_upload_id");
        if (bulkUploadId) {
            var isPollingActive = true,
                attempts = 0;

            var retry = function () {
                attempts += 1;
                setTimeout(pollStatus, 2000);
            };

            var pollStatus = function () {
                if (isPollingActive && attempts < 10) {
                    $.ajax({
                        url: '',
                        type: 'post',
                        dataType: 'json',
                        data: {
                            action: 'bulk',
                            upload_id: bulkUploadId,
                        },
                        error: function () {
                            retry();
                        },
                        success: function (data) {
                            if (data) {
                                if (data.inProgress) {
                                    isPollingActive = true;
                                    attempts = 0;
                                    $('#upload-progress').html(
                                        _.template($('#template-upload-progress').text())(data)
                                    );
                                    retry();
                                } else {
                                    isPollingActive = false;
                                    $('#upload-notice').html(
                                        _.template($('#template-bulk-status').text())(data)
                                    );
                                }
                            } else {
                                retry();
                            }
                        },
                    });
                } else {
                    if (attempts >= 10) {
                        $('#upload-notice').text(gettext("Sorry, it looks like the upload failed."));
                    }
                    isPollingActive = false;
                }
            };

            pollStatus();
        }
    });

    $(function () {
        var $editGroupName = $('#edit-group-name');
        $('#toggle-group-name').click(function (e) {
            $editGroupName.toggle();
            e.preventDefault();
        });
    });

    return 1;
});
