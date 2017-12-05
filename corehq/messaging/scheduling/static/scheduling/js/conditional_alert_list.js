hqDefine("scheduling/js/conditional_alert_list", function() {
    $(function() {
        var conditonal_alert_list_url = hqImport("hqwebapp/js/initial_page_data").reverse("conditional_alert_list");
        var loader_src = hqImport("hqwebapp/js/initial_page_data").get("loader_src");

        $("#conditional-alert-list").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": true,
            "serverSide": true,
            "ajaxSource": conditonal_alert_list_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_conditional_alerts"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no alerts to display.'),
                "infoEmpty": gettext('There are no alerts to display.'),
                "processing": '<img src="' + loader_src + '" /> ' + gettext('Loading alerts...'),
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
                    "render": function(data) {
                        return data ? gettext("Active") : gettext("Inactive");
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
    });
});
