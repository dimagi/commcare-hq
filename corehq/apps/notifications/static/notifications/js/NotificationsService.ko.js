/**
 * NotificationsService communicates with the NotificationsServiceRMIView django view
 * to fetch and update notifications for users on CommCare HQ.
 *
 */
(function ($, _, RMI) {
    'use strict';

    var Notification = function (data) {
        var self = this;
        self.isRead = ko.observable(data.isRead);
        self.content = ko.observable(data.content);
        self.url = ko.observable(data.url);
        self.type = ko.observable(data.type);
        self.date = ko.observable(data.date);

        self.isAlert = ko.computed(function () {
            return self.type() === 'alert';
        });
        self.isInfo = ko.computed(function () {
            return self.type() === 'info';
        });
    };

    var NotificationsServiceModel = function (rmi) {
        var self = this;
        self.notifications = ko.observableArray();
        self.hasUnread = ko.observable(false);
        self.hasError = ko.observable(false);

        self.init = function () {
            rmi("get_notifications", {'did_it_work': true})
                .done(function (data) {
                    _.each(data.notifications, function (data) {
                        self.notifications.push(new Notification(data));
                    });
                    self.hasUnread(data.hasUnread);
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown);
                    self.hasError(true);
                });
        };
    };

    $.fn.startNotificationsService = function (rmiUrl) {
        var csrfToken = $.cookie('csrftoken');
        var _rmi = RMI(rmiUrl, csrfToken);
        function rmi(remoteMethod, data) {
            return _rmi("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        }
        var viewModel = new NotificationsServiceModel(rmi);
        viewModel.init();
        $(this).koApplyBindings(viewModel);
    };

})($, _, RMI);


