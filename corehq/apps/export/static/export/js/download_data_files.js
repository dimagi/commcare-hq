hqDefine("export/js/download_data_files",[
    'jquery',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
], function ($, alertUserModule, initialPageData, assertProperties) {
    var alertUser = alertUserModule.alert_user;
    /**
     * Copies the URL of a data file to the clipboard
     *
     * The function will first attempt to copy the URL to the clipboard without
     * any further user interaction. If that fails, the user will be given a
     * dialog box with the URL selected, and prompted to press Ctrl-C and Enter.
     *
     * @param url: The URL to be copied to the clipboard
     * @param textareaElem: A hidden <textarea> element containing the URL
     */
    var copyDataFileUrl = function () {
        assertProperties.assertRequired($(this).data(), ['id', 'name']);

        var url =  window.location.origin + initialPageData.reverse('download_data_file',$(this).data("id"), $(this).data("name"));
        var textareaElem = $('#url_'.concat($(this).data("id")));

        var showCopyDialog = function () {
            window.prompt(gettext("Copy to clipboard: Ctrl-C, Enter (Mac: Cmd-C, Enter)"), url);
        };
        try {
            // Most browsers since Sept 2015
            textareaElem.show();
            textareaElem.select();
            var copied = document.execCommand("copy");
            textareaElem.hide();
            if (copied) {
                alertUser(gettext("Data file URL copied to clipboard."), "success", true);
            } else {
                showCopyDialog();
            }
        } catch (err) {
            // Older browsers
            showCopyDialog();
        }
    };

    /**
     * Makes an async DELETE request to url, and on success deletes rowElem.
     *
     * @param url: The URL to send the DELETE request to
     * @param rowElem: The <tr> element of the data file to remove on successful deletion
     */
    var deleteDataFile = function () {
        assertProperties.assertRequired($(this).data(), ['id','name']);
        var url = initialPageData.reverse('download_data_file', $(this).data("id"), $(this).data("name"));
        var rowElem = $('#row_'.concat($(this).data("id")));

        $.ajax({
            url: url,
            type: "DELETE",
            success: function () {
                rowElem.remove();
                alertUser(gettext("Data file deleted."), "success", true);
            },
        });
    };
    $(document).on('click', '.copy-data-file', copyDataFileUrl);
    $(document).on('click', '.delete-data-file', deleteDataFile);

});
