hqDefine('email/js/email_settings', [
    "jquery",
], function ($) {
    $(document).ready(function () {
        var saveButton = $('button[type="submit"]');
        var formModified = false;

        function handleFormChanges() {
            saveButton.prop('disabled', false);
            saveButton.text('Save');
            formModified = true;
        }

        function handleSaveClick() {
            if (!formModified) {
                return;
            }

            saveButton.prop('disabled', true);
            saveButton.text('Saving');
        }

        $('form :input').on('input', handleFormChanges);

        saveButton.on('click', handleSaveClick);

        saveButton.prop('disabled', true);
        saveButton.text('Saved');
    });
});
