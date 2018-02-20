var upcoming_table = null;  // needs to be accessible to global function delete_broadcast

hqDefine("reminders/js/broadcasts_list", function() {
    $(function() {
        var past_table,
            list_broadcasts_url = hqImport("hqwebapp/js/initial_page_data").reverse("list_broadcasts"),
            loader_src = hqImport("hqwebapp/js/initial_page_data").get("loader_src"),
            reminders_migration_in_progress = hqImport("hqwebapp/js/initial_page_data").get("reminders_migration_in_progress");

        upcoming_table = $("#upcoming-broadcasts-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 5,
            "processing": true,
            "serverSide": true,
            "ajaxSource": hqImport("hqwebapp/js/initial_page_data").reverse("list_broadcasts"),
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_upcoming"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no broadcasts to display.'),
                "infoEmpty": gettext('There are no broadcasts to display.'),
                "lengthMenu": gettext('Show _MENU_ broadcasts per page'),
                "processing": '<img src="' + loader_src + '" /> ' + gettext('Loading Broadcasts...'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ broadcasts'),
                "infoFiltered": gettext('(filtered from _MAX_ total broadcasts)'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "render": function(data, type, full) {
                        return '<a href="' + full[4] + '">' + full[0] + '</a>';
                    },
                },
                {
                    "targets": [3],
                    "render": function(data) {
                        return '<button class="btn btn-danger" onClick="delete_broadcast(\'' + data + '\');" '
                                    + (reminders_migration_in_progress ? 'disabled' : '') + '>'
                                    + gettext('Delete') + '</button>';
                    },
                },
            ],
        });
        past_table = $("#past-broadcasts-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 5,
            "processing": true,
            "serverSide": true,
            "ajaxSource": list_broadcasts_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_past"});
            },
            "dom": "rtp",
            "language": {
                "emptyTable": gettext('There are no broadcasts to display.'),
                "infoEmpty": gettext('There are no broadcasts to display.'),
                "lengthMenu": gettext('Show _MENU_ broadcasts per page'),
                "processing": '<img src="' + loader_src + '" /> ' + gettext('Loading Broadcasts...'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ broadcasts'),
                "infoFiltered": gettext('(filtered from _MAX_ total broadcasts)'),
            },
            "columnDefs": [
                {
                    "targets": [3],
                    "render": function(data, type, full) {
                        return '<a class="btn btn-primary" href="' + full[5] + '">' + gettext("Copy") + '</a>';
                    },
                },
            ],
        });
    });
});

function delete_broadcast(broadcast_id)  {
    if (confirm(gettext('Are you sure you want to delete this broadcast?'))) {
        $.ajax({
            url: hqImport("hqwebapp/js/initial_page_data").reverse("list_broadcasts"),
            type: "POST",
            data: {
                action: "delete_broadcast",
                broadcast_id: broadcast_id,
            },
        }).done(function(response, textStatus, jqXHR) {
            upcoming_table.fnDraw();
        });
    }
}
