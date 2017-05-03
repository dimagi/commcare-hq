/**
 * NotificationsService communicates with the NotificationsServiceRMIView django view
 * to fetch and update notifications for users on CommCare HQ.
 *
 */
(function ($, _, RMI) {
    'use strict';

    var Notification = function (data, rmi) {
        var self = this;
        self.id = ko.observable(data.id);
        self.isRead = ko.observable(data.isRead);
        self.content = ko.observable(data.content);
        self.url = ko.observable(data.url);
        self.type = ko.observable(data.type);
        self.date = ko.observable(data.date);
        self.activated = ko.observable(data.activated);

        self.isAlert = ko.computed(function () {
            return self.type() === 'alert';
        });
        self.isInfo = ko.computed(function () {
            return self.type() === 'info';
        });
        self.markAsRead = function() {
            rmi("mark_as_read", {id: self.id()});
            self.isRead(true);
            return true;
        };
    };

    var NotificationsServiceModel = function (rmi) {
        var self = this;
        self.notifications = ko.observableArray();
        self.hasError = ko.observable(false);
        self.lastSeenNotificationDate = ko.observable();

        self.hasUnread = ko.computed(function () {
            return _.some(self.notifications(), function(note) {
                return !note.isRead();
            });
        });

        self.seen = ko.computed(function() {

            if (!self.hasUnread()) {
                return true;
            }

            var notifications = self.notifications();
            if (notifications.length === 0) {
                return true;
            }

            var newestNotification = notifications[0];
            var newestNotificationDate = new Date(newestNotification.activated());
            var lastSeenNotificationDate = new Date(self.lastSeenNotificationDate());
            return lastSeenNotificationDate >= newestNotificationDate;
        });

        self.init = function () {
            rmi("get_notifications", {'did_it_work': true})
                .done(function (data) {
                    self.lastSeenNotificationDate(data.lastSeenNotificationDate);
                    _.each(data.notifications, function (data) {
                        self.notifications.push(new Notification(data, rmi));
                    });
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown);
                    self.hasError(true);
                });
        };

        self.bellClickHandler = function() {
            if (self.notifications().length === 0) {
                return;
            }

            rmi("save_last_seen", {"notification_id": self.notifications()[0].id()})
                .done(function(data) {
                    self.lastSeenNotificationDate(data.activated);
                })
                .fail(function(jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown); // eslint-disable-line no-console
                    self.hasError(true);
                });
        };
    };

    $.fn.startNotificationsService = function (rmiUrl) {
        var csrfToken = $("#csrfTokenContainer").val();
        var _rmi = RMI(rmiUrl, csrfToken);
        function rmi(remoteMethod, data) {
            return _rmi("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        }
        var viewModel = new NotificationsServiceModel(rmi);
        viewModel.init();
        $(this).koApplyBindings(viewModel);
        return viewModel;
    };

})($, _, RMI);
