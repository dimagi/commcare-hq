hqDefine("data_interfaces/js/manage_case_groups", function() {
    var bulkUploadId = hqImport("hqwebapp/js/initial_page_data").get("bulk_upload_id");
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
                    error: function (data) {
                        retry();
                    },
                    success: function (data) {
                        if (data) {
                            isPollingActive = false;
                            $('#upload-notice').html(
                                _.template($('#template-bulk-status').text())(data)
                            );
                        } else {
                            retry();
                        }
                    }
                });
            } else {
                if (attempts >= 10) {
                    $('#upload-notice').text(gettext("Sorry, it looks like the upload failed."));
                }
                isPollingActive = false;
            }
        };
        $(function () {
            pollStatus();
        });
    }

    $(function () {
        var $editGroupName = $('#edit-group-name');
        $('#toggle-group-name').click(function (e) {
            $editGroupName.toggle();
            e.preventDefault();
        });
    });
});
