hqDefine("scheduling/js/broadcasts_list", [
    'jquery',
    'knockout',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'datatables',
    'datatables.fixedColumns',
    'datatables.bootstrap',
], function (
    $,
    ko,
    assertProperties,
    initialPageData
) {
    var broadcast = function (options) {
        var self = ko.mapping.fromJS(options);

        self.editUrl = initialPageData.reverse('edit_schedule', self.type, self.id());

        self.activateBroadcast = function () {
            alert("TODO: activate_scheduled_broadcast " + self.id());
        };

        self.deactivateBroadcast = function () {
            alert("TODO: deactivate_scheduled_broadcast " + self.id());
        };

        self.deleteBroadcast = function () {
            alert("TODO: delete " + self.id());
        };

        return self;
    };

    var broadcastList = function (options) {
        assertProperties.assert(options, ['listAction', 'type'], []);

        var self = {};
        self.broadcasts = ko.observableArray();

        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();
        self.showPaginationSpinner = ko.observable(false);

        self.emptyTable = ko.computed(function () {
            return self.totalItems() === 0;
        });
        self.currentPage = ko.observable(1);
        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
            self.currentPage(page);
            $.ajax({
                url: initialPageData.reverse("new_list_broadcasts"),
                data: {
                    action: options.listAction,
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.showPaginationSpinner(false);
                    self.broadcasts(_.map(data.broadcasts, function (b) {
                        return broadcast(_.extend(b, {
                            type: options.type,
                        }));
                    }));
                    self.totalItems(data.total);
                },
            });
        };

        self.goToPage(self.currentPage());

        return self;
    };

    $(function () {
        var $scheduledTable = $("#scheduled-table");
        if ($scheduledTable.length) {
            $scheduledTable.koApplyBindings(broadcastList({
                listAction: 'list_scheduled',
                type: 'scheduled',
            }));
        }

        var $immediateTable = $("#immediate-table");
        if ($immediateTable.length) {
            $immediateTable.koApplyBindings(broadcastList({
                listAction: 'list_immediate',
                type: 'immediate',
            }));
        }
    });

    /*var scheduledTable = null;

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
        });
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
    }*/
});
