hqDefine("scheduling/js/conditional_alert_list", function() {
    $(function() {
        var conditonal_alert_list_url = hqImport("hqwebapp/js/initial_page_data").reverse("conditional_alert_list");

        var table = $("#conditional-alert-list").dataTable({
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
                    "render": function() {
                        return 'Delete button';
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
                        var id = row[row.length - 1];
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
                    "render": function() {
                        return 'Activate or Deactivate button';
                    },
                },
            ],
        });

        function reloadTable() {
            table.fnDraw(false);
            setTimeout(reloadTable, 10000);
        };

        setTimeout(reloadTable, 10000);

    });
});
