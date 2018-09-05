hqDefine("scheduling/js/conditional_alert_list", [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function($, initialPageData) {
    var table = null;

    $(function() {
        var conditonalAlterListUrl = initialPageData.reverse("conditional_alert_list");

        table = $("#conditional-alert-list").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": conditonalAlterListUrl,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_conditional_alerts"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no alerts to display.'),
                "infoEmpty": gettext('There are no alerts to display.'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ alerts'),
            },
            "columns": [
                {"data": ""},
                {"data": "name"},
                {"data": "case_type"},
                {"data": "active"},
                {"data": ""},
            ],
            "columnDefs": [
                {
                    "targets": [0],
                    "className": "text-center",
                    "render": function(data, type, row) {
                        var button_id = 'delete-button-for-' + row.id;
                        var disabled = row.locked_for_editing ? 'disabled' : '';
                        return '<button id="' + button_id + '" \
                                        class="btn btn-danger alert-delete" \
                                        data-id="'+row.id+'"\
                                        ' + disabled + '> \
                                <i class="fa fa-remove"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var url = initialPageData.reverse('edit_conditional_alert', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function(data, type, row) {
                        var active_text = '';
                        if(row.active) {
                            active_text = '<span class="label label-success">' + gettext("Active") + '</span> ';
                        } else {
                            active_text = '<span class="label label-danger">' + gettext("Inactive") + '</span> ';
                        }

                        var processing_text = '';
                        if(row.locked_for_editing) {
                            processing_text = '<span class="label label-default">' + gettext("Rule is processing") + ': ' + row.progress_pct + '%</span> ';
                        }

                        return active_text + processing_text;
                    },
                },
                {
                    "targets": [4],
                    "render": function(data, type, row) {
                        var html = null;
                        var button_id = 'activate-button-for-' + row.id;
                        var disabled = (row.locked_for_editing || !row.editable) ? 'disabled' : '';
                        if(row.active) {
                            html = '<button id="' + button_id + '" \
                                            class="btn btn-default alert-activate" \
                                            data-id="'+row.id+'"\
                                            data-action="deactivate"\
                                            ' + disabled + '> \
                                   ' + gettext("Deactivate") + '</button>';
                        } else {
                            html = '<button id="' + button_id + '" + \
                                            class="btn btn-default alert-activate" + \
                                            data-action="activate"\
                                            data-id="'+row.id+'"\
                                            ' + disabled + '> \
                                   ' + gettext("Activate") + '</button>';
                        }

                        if(row.locked_for_editing) {
                            html += ' <button class="btn btn-default alert-restart" data-id="'+row.id+'" >';
                            html += '<i class="fa fa-refresh"></i> ' + gettext("Restart Rule") + '</button>';
                        }

                        return html;
                    },
                },
                {
                    "targets": [5],
                    "visible": initialPageData.get("allow_copy"),
                    "render": function(data, type, row) {
                        var disabled = (row.locked_for_editing || !row.editable) ? 'disabled' : '';
                        var html = '<input type="text" id="copy-to-project-for-' + row.id + '" placeholder="' + gettext("Project") + '" class="textinput textInput form-control" />';
                        html += ' <button ' + disabled + ' id="copy-button-for-' + row.id + '" class="btn btn-default alert-copy" data-id="' + row.id + '" >' + gettext("Copy") + '</button>';
                        return html;
                    },
                },
            ],
        });

        $(document).on('click', '.alert-delete', deleteAlert);
        $(document).on('click', '.alert-activate', activateAlert);
        $(document).on('click', '.alert-restart', restartRule);
        $(document).on('click', '.alert-copy', copyRule);

        function reloadTable() {
            table.fnDraw(false);
            setTimeout(reloadTable, 10000);
        }

        setTimeout(reloadTable, 10000);

    });

    function alertAction(action, rule_id, projectName) {
        var activateButton = $('#activate-button-for-' + rule_id);
        var deleteButton = $('#delete-button-for-' + rule_id);
        var copyButton = $('#copy-button-for-' + rule_id);
        if(action === 'delete') {
            deleteButton.disableButton();
            activateButton.prop('disabled', true);
            copyButton.prop('disabled', true);
        } else if (action === 'activate' || action === 'deactivate') {
            activateButton.disableButton();
            deleteButton.prop('disabled', true);
            copyButton.prop('disabled', true);
        } else if(action === 'copy') {
            copyButton.disableButton();
            deleteButton.prop('disabled', true);
            activateButton.prop('disabled', true);
        }

        var payload = {
            action: action,
            rule_id: rule_id,
        };

        if(action === 'copy') {
            payload['project'] = projectName;
        }

        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: payload,
        })
            .done(function(result) {
                if(action === 'restart') {
                    if(result.status === 'success') {
                        alert(gettext("This rule has been restarted."));
                    } else if(result.status === 'error') {
                        var text = gettext(
                            "Unable to restart rule. Rules can only be started every two hours and there are " +
                            "%s minute(s) remaining before this rule can be started again."
                        );
                        text = interpolate(text, [result.minutes_remaining]);
                        alert(text);
                    }
                } else if(action === 'copy') {
                    if(result.status === 'success') {
                        alert(gettext("Copy successful."));
                    } else if(result.status === 'error') {
                        alert(interpolate(gettext("Error: %s"), [result.error_msg]));
                    }
                }
            })
            .always(function() {
                table.fnDraw(false);
            });
    }

    function activateAlert() {
        alertAction($(this).data("action"), $(this).data("id"));
    }


    function deleteAlert() {
        if(confirm(gettext("Are you sure you want to delete this conditional message?"))) {
            alertAction('delete', $(this).data("id"));
        }
    }

    function restartRule(rule_id) {
        var prompt = null;
        if(initialPageData.get("limit_rule_restarts")) {
            prompt = gettext(
                "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                "You will only be able to restart this rule once every two hours. Restart this rule?"
            );
        } else {
            prompt = gettext(
                "A rule should only be restarted when you believe it is stuck and is not progressing. " +
                "Your user is able to restart as many times as you like, but restarting too many times without " +
                "finishing can place a burden on the system. Restart this rule?"
            );
        }
        if(confirm(prompt)) {
            alertAction('restart', $(this).data("id"));
        }
    }

    function copyRule() {
        var ruleId = $(this).data("id");
        var projectName = $.trim($("#copy-to-project-for-" + ruleId).val());

        if(projectName === '') {
            alert(gettext("Please enter a project name first."));
            return;
        }

        if(confirm(interpolate(gettext("Copy this alert to project %s?"), [projectName]))) {
            alertAction('copy', ruleId, projectName);
        }
    }

});
