hqDefine("scheduling/js/broadcasts_list", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'datatables',
    'datatables.fixedColumns',
    'datatables.bootstrap',
], function (
    $,
    initialPageData
) {
    var scheduledTable = null;

    $(function () {
        var listBroadcastsUrl = initialPageData.reverse("new_list_broadcasts");

        scheduledTable = $("#scheduled-table").dataTable({
            "lengthChange": false,
            "filter": false,
            "sort": false,
            "displayLength": 10,
            "processing": false,
            "serverSide": true,
            "ajaxSource": listBroadcastsUrl,
            "fnServerParams": function (aoData) {
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
                    "render": function (data, type, row) {
                        return '<button data-id="' + row.id + '" class="btn btn-danger broadcast-delete">'
                                + '<i class="fa fa-remove"></i></button>';
                    },
                },
                {
                    "targets": [1],
                    "render": function (data, type, row) {
                        var url = initialPageData.reverse('edit_schedule', 'scheduled', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
                {
                    "targets": [3],
                    "render": function (data, type, row) {
                        if (row.active) {
                            return '<span class="label label-success">' + gettext("Active") + '</span>';
                        } else {
                            return '<span class="label label-danger">' + gettext("Inactive") + '</span>';
                        }
                    },
                },
                {
                    "targets": [4],
                    "render": function (data, type, row) {
                        var disabled = row.editable ? '' : ' disabled ';
                        if (row.active) {
                            return '<button data-id="' + row.id + '"' + disabled + 'data-action="deactivate_scheduled_broadcast" class="btn btn-default broadcast-activate">'
                                   + gettext("Deactivate") + '</button>';
                        } else {
                            return '<button data-id="' + row.id + '"' + disabled + 'data-action="activate_scheduled_broadcast" class="btn btn-default broadcast-activate">'
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
            "ajaxSource": listBroadcastsUrl,
            "fnServerParams": function (aoData) {
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
                    "render": function (data, type, row) {
                        var url = initialPageData.reverse('edit_schedule', 'immediate', row.id);
                        return "<a href='" + url + "'>" + row.name + "</a>";
                    },
                },
            ],
        });

        $(document).on('click', '.broadcast-activate', activateScheduledBroadcast);
        $(document).on('click', '.broadcast-delete', deleteScheduledBroadcast);
    });

    function broadcastAction(action, button) {
        var broadcastId = $(button).data("id"),
            $row = $(button).closest("tr"),
            $activateButton = $row.find(".broadcast-activate"),
            $deleteButton = $row.find(".broadcast-delete");
        if (action === 'delete_scheduled_broadcast') {
            $deleteButton.disableButton();
            $activateButton.prop('disabled', true);
        } else {
            $activateButton.disableButton();
            $deleteButton.prop('disabled', true);
        }

        $.ajax({
            url: '',
            type: 'post',
            dataType: 'json',
            data: {
                action: action,
                broadcast_id: broadcastId,
            },
        })
            .always(function () {
                scheduledTable.fnDraw(false);
            });
    }

    function activateScheduledBroadcast() {
        broadcastAction($(this).data("action"), this);
    }

    function deleteScheduledBroadcast() {
        if (confirm(gettext("Are you sure you want to delete this scheduled message?"))) {
            broadcastAction('delete_scheduled_broadcast', this);
        }
    }
});
