"use strict";
hqDefine("groups/js/group_members", [
    "jquery",
    "underscore",
    "analytix/js/google",
    "es6!hqwebapp/js/bootstrap5_loader",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap5/alert_user",
    "hqwebapp/js/ui_elements/bootstrap5/ui-element-key-val-list",
    "hqwebapp/js/select_2_ajax_widget",     // "Group Membership" select2
    "hqwebapp/js/components/select_toggle",            // select toggle for "Edit Setings" popup
], function (
    $,
    _,
    googleAnalytics,
    bootstrap,
    initialPageData,
    alertUser,
    uiMapList
) {
    $(function () {
        var customDataEditor = uiMapList.new(initialPageData.get("group_id"), gettext("Edit Group Information"));
        customDataEditor.val(initialPageData.get("group_metadata"));
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
        $("button:submit", $deleteGroupModalForm).click(function () {
            googleAnalytics.track.event("Editing Group", "Deleted Group", initialPageData.get("group_id"), "", {}, function () {
                $deleteGroupModalForm.submit();
            });
            return false;
        });

        $(window).on('beforeunload', function () {
            var someUnsavedChanges = false;
            var ret = gettext("The following changes will not be saved: ");

            for (var key in unsavedChanges) {
                if (_.has(unsavedChanges, key) && unsavedChanges[key]) {
                    ret += "\n" + key;
                    someUnsavedChanges = true;
                }
            }

            if (someUnsavedChanges) {
                return ret;
            }

            return;
        });

        function outcome(isSuccess, name, id, gaEventLabel, additionalCallback) {
            return function () {
                var message;
                if (isSuccess) {
                    message = gettext('Successfully saved ') + name.toLowerCase() + '.';
                    unsavedChanges[name] = false;
                } else {
                    message = gettext('Failed to save ') + name.toLowerCase() + '.';
                }
                $(id).find(':button').enableButton();
                alertUser.alert_user(message, isSuccess ? 'success' : 'danger');
                bootstrap.Modal.getOrCreateInstance(document.getElementById('editGroupSettings')).hide();

                if (_.isFunction(additionalCallback)) {
                    additionalCallback();
                }

                if (gaEventLabel) {
                    googleAnalytics.track.event('Editing Group', gaEventLabel, initialPageData.get("group_id"));
                }

                if (initialPageData.get('show_disable_case_sharing')) {
                    setTimeout(function () {
                        location.reload();
                    }, 500);
                }
            };
        }

        $(function () {
            $('#edit_membership').submit(function () {
                var _showMembershipUpdating = function () {
                        $('#edit_membership').fadeOut();
                        $('#membership_updating').removeClass("d-none");
                    },
                    _hideMembershipUpdating = function () {
                        $('#edit_membership').fadeIn();
                        $('#membership_updating').addClass("d-none");
                    };
                _showMembershipUpdating();
                $(this).find(':button').prop('disabled', true);

                const formData = new FormData(this);
                let ajaxData = Object.fromEntries(formData);
                // Object.fromEntries uses get, but selected_ids has multiple values and needs getAll
                ajaxData.selected_ids = formData.getAll("selected_ids");

                $.ajax({
                    url: $(this).attr("action"),
                    method: "POST",
                    data: ajaxData,
                    success: outcome(true, "Group membership", "#edit_membership", "Edit Group Membership", _hideMembershipUpdating),
                    error: outcome(false, "Group membership", "#edit_membership", _hideMembershipUpdating),
                });
                return false;
            });
            $('#edit-group-settings').submit(function () {
                $(this).find('.modal-footer :button').disableButton();
                $.ajax({
                    url: $(this).attr("action"),
                    method: "POST",
                    data: Object.fromEntries(new FormData(this)),
                    success: outcome(true, "Group settings", "#edit-group-settings", "Edit Settings"),
                    error: outcome(false, "Group settings", "#edit-group-settings"),
                });
                return false;
            });
            $('#group-case-sharing-input').change(function () {
                if ($('#group-case-sharing-input').val() === 'true' && !initialPageData.get("domain_uses_case_sharing")) {
                    $('#group-case-sharing-warning').prop("hidden", false);
                } else {
                    $('#group-case-sharing-warning').prop('hidden', true);
                }
            });
            $('#group-data-form').submit(function () {
                $(this).find(':button').prop('disabled', true);
                $.ajax({
                    url: $(this).attr("action"),
                    method: "POST",
                    data: Object.fromEntries(new FormData(this)),
                    success: outcome(true, "Group data", "#group-data-form", "Edit Group Data"),
                    error: outcome(false, "Group data", "#group-data-form"),
                });
                return false;
            });
        });

        $('#initiate-verification-workflow').submit(function () {
            var button = $('#submit-verification');
            button.prop('disabled', true);
            button.text(gettext("Please wait and do not navigate away..."));
        });
    });
});
