hqDefine("scheduling/js/broadcasts_list", [
    'jquery',
    'knockout',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/components.ko",     // pagination
], function (
    $,
    ko,
    assertProperties,
    initialPageData
) {
    var broadcast = function (options) {
        var self = ko.mapping.fromJS(options);

        self.editUrl = initialPageData.reverse('edit_schedule', self.type(), self.id());
        self.actionInProgress = ko.observable(false);

        self.activateBroadcast = function (model) {
            self.broadcastAction('activate_scheduled_broadcast', model);
        };

        self.deactivateBroadcast = function (model) {
            self.broadcastAction('deactivate_scheduled_broadcast', model);
        };

        self.deleteBroadcast = function (model) {
            if (confirm(gettext("Are you sure you want to delete this scheduled message?"))) {
                self.broadcastAction('delete_scheduled_broadcast', model);
            }
        };

        self.broadcastAction = function (action, model) {
            self.actionInProgress(true);
            $.ajax({
                url: '',
                type: 'post',
                dataType: 'json',
                data: {
                    action: action,
                    broadcast_id: model.id(),
                },
                success: function (data) {
                    ko.mapping.fromJS(data.broadcast, self);
                },
            }).always(function () {
                self.actionInProgress(false);
            });
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

        self.onPaginationLoad = function () {
            self.goToPage(self.currentPage());
        };

        return self;
    };

    $(function () {
        var $scheduledList = $("#scheduled-broadcasts");
        if ($scheduledList.length) {
            $scheduledList.koApplyBindings(broadcastList({
                listAction: 'list_scheduled',
                type: 'scheduled',
            }));
        }

        var $immediateList = $("#immediate-broadcasts");
        if ($immediateList.length) {
            $immediateList.koApplyBindings(broadcastList({
                listAction: 'list_immediate',
                type: 'immediate',
            }));
        }
    });
});
