/* globals hqDefine, django, $, alert_user */
hqDefine("export/js/download_data_files.js", function() {

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
    var copyDataFileUrl = function (url, textareaElem) {
        var showCopyDialog = function () {
            window.prompt(django.gettext("Copy to clipboard: Ctrl-C, Enter (Mac: Cmd-C, Enter)"), url);
        };
        try {
            // Most browsers since Sept 2015
            textareaElem.show();
            textareaElem.select();
            var copied = document.execCommand("copy");
            textareaElem.hide();
            if (copied) {
                alert_user(django.gettext("Data file URL copied to clipboard."), "success", true);
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
    var deleteDataFile = function (url, rowElem) {
        $.ajax({
            url: url,
            type: "DELETE",
            success: function () {
                rowElem.remove();
                alert_user(django.gettext("Data file deleted."), "success", true);
            },
        });
    };

    return {
        copyDataFileUrl: copyDataFileUrl,
        deleteDataFile: deleteDataFile,
    };
});
