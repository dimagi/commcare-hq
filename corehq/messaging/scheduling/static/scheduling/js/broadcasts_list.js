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
            "columns": [
                {"data": ""},
                {"data": "name"},
                {"data": "last_sent"},
                {"data": "active"},
                {"data": ""},
            ],
            "columnDefs": [
                {
                    "targets": [0],
                    "className": "text-center",
                    "render": function(data, type, row) {
                        var button_id = 'delete-button-for-scheduled-broadcast-' + row.id;
                        return '<button id="' + button_id + '" \
                                        class="btn btn-danger" \
                                        onclick="hqImport(\'scheduling/js/broadcasts_list\').deleteScheduledBroadcast(' + row.id + ')"> \
                                <i class="fa fa-remove"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'scheduled', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function(data, type, row) {
                        if(row.active) {
                            return '<span class="label label-success">' + gettext("Active") + '</span>';
                        } else {
                            return '<span class="label label-danger">' + gettext("Inactive") + '</span>';
                        }
                    },
                },
                {
                    "targets": [4],
                    "render": function(data, type, row) {
                        var disabled = row.editable ? '' : ' disabled ';
                        var button_id = 'activate-button-for-scheduled-broadcast-' + row.id;
                        if(row.active) {
                            return '<button id="' + button_id + '"' + disabled + '\
                                            class="btn btn-default" \
                                            onclick="hqImport(\'scheduling/js/broadcasts_list\').deactivateScheduledBroadcast(' + row.id + ')"> \
                                   ' + gettext("Deactivate") + '</button>';
                        } else {
                            return '<button id="' + button_id + '"' + disabled + '\
                                            class="btn btn-default" + \
                                            onclick="hqImport(\'scheduling/js/broadcasts_list\').activateScheduledBroadcast(' + row.id + ')"> \
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
            "columns": [
                {"data": "name"},
                {"data": "last_sent"},
            ],
            "columnDefs": [
                {
                    "targets": [0],
                    "render": function(data, type, row) {
                        var url = hqImport("hqwebapp/js/initial_page_data").reverse('edit_schedule', 'immediate', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
            ],
        });
    });

    function broadcastAction(action, broadcast_id) {
        var activateButton = $('#activate-button-for-scheduled-broadcast-' + broadcast_id);
        var deleteButton = $('#delete-button-for-scheduled-broadcast-' + broadcast_id);
        if(action === 'delete_scheduled_broadcast') {
            deleteButton.disableButton();
            activateButton.prop('disabled', true);
        } else {
            activateButton.disableButton();
            deleteButton.prop('disabled', true);
        }

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
