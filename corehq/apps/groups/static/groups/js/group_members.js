/* globals django */
hqDefine("groups/js/group_members", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

    // Multiselect widget
    $(function () {
        var multiselect_utils = hqImport('style/js/multiselect_utils');
        multiselect_utils.createFullMultiselectWidget(
            'id_selected_ids',
            django.gettext("Available Workers"),
            django.gettext("Workers in Group"),
            django.gettext("Search Workers...")
        );
    });

    $(function () {
        // custom data
        var customDataEditor = hqImport('style/js/ui-element').map_list(initial_page_data("group_id"), gettext("Group Information"));
        customDataEditor.val(initial_page_data("group_metadata"));
        customDataEditor.on("change", function () {
            $("#group-data").val(JSON.stringify(this.val()));
        });
        $("#group-data-ui-editor").append(customDataEditor.ui);

        // "are you sure?" stuff
        var unsavedChanges = {};

        $("#edit_membership").change(function () {
            unsavedChanges["Group membership"] = true;
        });

        $("#edit-group-settings").change(function () {
            unsavedChanges["Group settings"] = true;
        });

        $("#group-data-form").change(function () {
            unsavedChanges["Group data"] = true;
        });

        // Delete group event
        var $deleteGroupModalForm = $("#delete_group_modal form");
        $("button:submit", $deleteGroupModalForm).click(function(){
            ga_track_event("Editing Group", "Deleted Group", initial_page_data("group_id"), {
                'hitCallback': function() {
                    $deleteGroupModalForm.submit();
                },
            });
            return false;
        });

        $(window).on('beforeunload', function () {
            var someUnsavedChanges = false;
            var ret = gettext("The following changes will not be saved: ");

            for (var key in unsavedChanges) {
                if (unsavedChanges.hasOwnProperty(key) && unsavedChanges[key]) {
                    ret += "\n" + key;
                    someUnsavedChanges = true;
                }
            }

            if (someUnsavedChanges) {
                return ret;
            }

            return;
        });

        function outcome(isSuccess, name, id, gaEventLabel) {
            return function() {
                var alertClass, message;
                if (isSuccess) {
                    alertClass = 'alert-success';
                    message = django.gettext('Successfully saved ') + name.toLowerCase() + '.';
                    unsavedChanges[name] = false;
                } else {
                    alertClass = 'alert-danger';
                    message = django.gettext('Failed to save ') + name.toLowerCase() + '.';
                }
                $(id).find(':button').enableButton();
                $('#save-alert').removeClass('alert-error alert-success alert-info').addClass(alertClass);
                $('#save-alert').html(message).show();
                $('#editGroupSettings').modal('hide');
                if (gaEventLabel){
                    ga_track_event('Editing Group', gaEventLabel, initial_page_data("group_id"));
                }
            };
        }

        $(function() {
            $('#edit_membership').submit(function() {
                $(this).find(':button').prop('disabled', true);
                $(this).ajaxSubmit({
                    success: outcome(true, "Group membership", "#edit_membership", "Edit Group Membership"),
                    error: outcome(false, "Group membership", "#edit_membership"),
                });
                return false;
            });
            $('#edit-group-settings').submit(function() {
                $(this).find(':button').disableButton();
                $(this).ajaxSubmit({
                    success: outcome(true, "Group settings", "#edit-group-settings", "Edit Settings"),
                    error: outcome(false, "Group settings", "#edit-group-settings"),
                });
                return false;
            });
            $('#group-case-sharing-input').change(function() {
                if($('#group-case-sharing-input').val() === 'true' && !initial_page_data("domain_uses_case_sharing")) {
                    $('#group-case-sharing-warning').prop("hidden", false);
                } else {
                    $('#group-case-sharing-warning').prop('hidden', true);
                }
            });
            $('#group-data-form').submit(function() {
                $(this).find(':button').prop('disabled', true);
                $(this).ajaxSubmit({
                    success: outcome(true, "Group data", "#group-data-form", "Edit Group Data"),
                    error: outcome(false, "Group data", "#group-data-form"),
                });
                return false;
            });
        });

        $('#initiate-verification-workflow').submit(function() {
            var button = $('#submit-verification');
            button.prop('disabled', true);
            button.text(gettext("Please wait and do not navigate away..."));
        });
    });
});
