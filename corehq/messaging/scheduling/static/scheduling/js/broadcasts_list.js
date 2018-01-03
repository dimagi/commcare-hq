hqDefine("scheduling/js/broadcasts_list", function() {

    var scheduledTable = null;

    $(function() {
        var list_broadcasts_url = hqImport("hqwebapp/js/initial_page_data").reverse("new_list_broadcasts");

        scheduledTable = $("#scheduled-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": list_broadcasts_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_scheduled"});
            },
            "sDom": "rtp",
            "language": {
                "emptyTable": gettext('There are no messages to display.'),
                "infoEmpty": gettext('There are no messages to display.'),
                "lengthMenu": gettext('Show _MENU_ messages per page'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ broadcasts'),
                "infoFiltered": gettext('(filtered from _MAX_ total broadcasts)'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "className": "text-center",
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var button_id = 'delete-button-for-scheduled-broadcast-' + id;
                        return '<button id="' + button_id + '" \
                                        class="btn btn-danger" \
                                        onclick="hqImport(\'scheduling/js/broadcasts_list\').deleteScheduledBroadcast(' + id + ')"> \
                                <i class="fa fa-remove" aria-hidden="true"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'scheduled', id);
                        return "<a href='" + url + "'>" + data + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function(data) {
                        if(data) {
                            return '<span class="label label-success">' + gettext("Active") + '</span>';
                        } else {
                            return '<span class="label label-danger">' + gettext("Inactive") + '</span>';
                        }
                    },
                },
                {
                    "targets": [4],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var button_id = 'activate-button-for-scheduled-broadcast-' + id;
                        var active = row[3];
                        if(active) {
                            return '<button id="' + button_id + '" \
                                            class="btn btn-default" \
                                            onclick="hqImport(\'scheduling/js/broadcasts_list\').deactivateScheduledBroadcast(' + id + ')"> \
                                   ' + gettext("Deactivate") + '</button>';
                        } else {
                            return '<button id="' + button_id + '" + \
                                            class="btn btn-default" + \
                                            onclick="hqImport(\'scheduling/js/broadcasts_list\').activateScheduledBroadcast(' + id + ')"> \
                                   ' + gettext("Activate") + '</button>';
                        }
                    },
                },
            ],
        });

        $("#immediate-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": list_broadcasts_url,
            "fnServerParams": function(aoData) {
                aoData.push({"name": "action", "value": "list_immediate"});
            },
            "dom": "rtp",
            "language": {
                "emptyTable": gettext('There are no messages to display.'),
                "infoEmpty": gettext('There are no messages to display.'),
                "lengthMenu": gettext('Show _MENU_ messages per page'),
                "info": gettext('Showing _START_ to _END_ of _TOTAL_ messages'),
                "infoFiltered": gettext('(filtered from _MAX_ total messages)'),
            },
            "columnDefs": [
                {
                    "targets": [0],
                    "render": function(data, type, row) {
                        var id = row[row.length - 1];
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'immediate', id);
                        return "<a href='" + url + "'>" + data + "</a>";
                    },
                },
            ],
        });
    });

    function broadcastAction(action, broadcast_id) {
        $('#activate-button-for-scheduled-broadcast-' + broadcast_id).prop('disabled', true);
        $('#delete-button-for-scheduled-broadcast-' + broadcast_id).prop('disabled', true);

        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: {
                action: action,
                broadcast_id: broadcast_id,
            },
        })
        .always(function() {
            scheduledTable.fnDraw(false);
        });
    }

    function activateScheduledBroadcast(broadcast_id) {
        broadcastAction('activate_scheduled_broadcast', broadcast_id);
    }

    function deactivateScheduledBroadcast(broadcast_id) {
        broadcastAction('deactivate_scheduled_broadcast', broadcast_id);
    }

    function deleteScheduledBroadcast(broadcast_id) {
        if(confirm(gettext("Are you sure you want to delete this scheduled message?"))) {
            broadcastAction('delete_scheduled_broadcast', broadcast_id);
        }
    }

    return {
        activateScheduledBroadcast: activateScheduledBroadcast,
        deactivateScheduledBroadcast: deactivateScheduledBroadcast,
        deleteScheduledBroadcast: deleteScheduledBroadcast,
    };
});
