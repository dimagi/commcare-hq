hqDefine("scheduling/js/broadcasts_list", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'datatables',
    'datatables.fixedColumns',
    'datatables.bootstrap',
], function(
    $,
    initialPageData
) {
    var scheduledTable = null;

    $(function() {
        var list_broadcasts_url = initialPageData.reverse("new_list_broadcasts");

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
                        return '<button data-id="' + row.id + '" class="btn btn-danger broadcast-delete">'
                                + '<i class="fa fa-remove"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function(data, type, row) {
                        var url = initialPageData.reverse('edit_schedule', 'scheduled', row.id);
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
                        if (row.active) {
                            return '<button data-id="' + row.id + '"' + disabled + 'class="btn btn-default broadcast-deactivate">'
                                   + gettext("Deactivate") + '</button>';
                        } else {
                            return '<button data-id="' + row.id + '"' + disabled + 'class="btn btn-default broadcast-activate">'
                                   + gettext("Activate") + '</button>';
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
                        var url = initialPageData.reverse('edit_schedule', 'immediate', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
            ],
        });

        $(document).on('click', '.broadcast-activate', activateScheduledBroadcast);
        $(document).on('click', '.broadcast-deactivate', deactivateScheduledBroadcast);
        $(document).on('click', '.broadcast-delete', deleteScheduledBroadcast);
    });

    function broadcastAction(action, element) {
        var broadcast_id = $(element).data("id");
        var activateButton = $('#activate-button-for-scheduled-broadcast-' + broadcast_id);
        var deleteButton = $('#delete-button-for-scheduled-broadcast-' + broadcast_id);
        if (action === 'delete_scheduled_broadcast') {
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

    function activateScheduledBroadcast() {
        broadcastAction('activate_scheduled_broadcast', this);
    }

    function deactivateScheduledBroadcast() {
        broadcastAction('deactivate_scheduled_broadcast', this);
    }

    function deleteScheduledBroadcast() {
        if(confirm(gettext("Are you sure you want to delete this scheduled message?"))) {
            broadcastAction('delete_scheduled_broadcast', this);
        }
    }
});
