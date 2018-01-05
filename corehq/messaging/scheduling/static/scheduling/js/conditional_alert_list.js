hqDefine("scheduling/js/conditional_alert_list", function() {
    var table = null;

    $(function() {
        var conditonal_alert_list_url = hqImport("hqwebapp/js/initial_page_data").reverse("conditional_alert_list");

        table = $("#conditional-alert-list").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": conditonal_alert_list_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_conditional_alerts"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no alerts to display.'),
                "infoEmpty": gettext('There are no alerts to display.'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ alerts'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "className": "text-center",
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var button_id = 'delete-button-for-' + id;
                        var locked_for_editing = row[row.length - 3];
                        var disabled = locked_for_editing ? 'disabled' : '';
                        return '<button id="' + button_id + '" \
                                        class="btn btn-danger" \
                                        onclick="hqImport(\'scheduling/js/conditional_alert_list\').deleteAlert(' + id + ')" \
                                        ' + disabled + '> \
                                <i class="fa fa-remove"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_conditional_alert', id);
                        return "<a href='" + url + "'>" + data + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function(data, type, row) {
                        var locked_for_editing = row[row.length - 3];
                        var rule_progress_pct = row[row.length - 2];

                        var active_text = '';
                        if(data) {
                            active_text = '<span class="label label-success">' + gettext("Active") + '</span> ';
                        } else {
                            active_text = '<span class="label label-danger">' + gettext("Inactive") + '</span> ';
                        }

                        var processing_text = '';
                        if(locked_for_editing) {
                            processing_text = '<span class="label label-default">' + gettext("Rule is processing") + ': ' + rule_progress_pct + '%</span> ';
                        }

                        return active_text + processing_text;
                    },
                },
                {
                    "targets": [4],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var button_id = 'activate-button-for-' + id;
                        var active = row[3];
                        var locked_for_editing = row[row.length - 3];
                        var disabled = locked_for_editing ? 'disabled' : '';
                        if(active) {
                            return '<button id="' + button_id + '" \
                                            class="btn btn-default" \
                                            onclick="hqImport(\'scheduling/js/conditional_alert_list\').deactivateAlert(' + id + ')" \
                                            ' + disabled + '> \
                                   ' + gettext("Deactivate") + '</button>';
                        } else {
                            return '<button id="' + button_id + '" + \
                                            class="btn btn-default" + \
                                            onclick="hqImport(\'scheduling/js/conditional_alert_list\').activateAlert(' + id + ')" \
                                            ' + disabled + '> \
                                   ' + gettext("Activate") + '</button>';
                        }
                    },
                },
            ],
        });

        function reloadTable() {
            table.fnDraw(false);
            setTimeout(reloadTable, 10000);
        }

        setTimeout(reloadTable, 10000);

    });

    function alertAction(action, rule_id) {
        $('#activate-button-for-' + rule_id).prop('disabled', true);
        $('#delete-button-for-' + rule_id).prop('disabled', true);

        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: {
                action: action,
                rule_id: rule_id,
            },
        })
        .always(function() {
            table.fnDraw(false);
        });
    }

    function activateAlert(rule_id) {
        alertAction('activate', rule_id);
    }

    function deactivateAlert(rule_id) {
        alertAction('deactivate', rule_id);
    }

    function deleteAlert(rule_id) {
        if(confirm(gettext("Are you sure you want to delete this conditional message?"))) {
            alertAction('delete', rule_id);
        }
    }

    return {
        activateAlert: activateAlert,
        deactivateAlert: deactivateAlert,
        deleteAlert: deleteAlert,
    };
});
