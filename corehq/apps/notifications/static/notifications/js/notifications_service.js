/**
 * NotificationsService communicates with the NotificationsServiceRMIView django view
 * to fetch and update notifications for users on CommCare HQ.
 *
 */

/* globals RMI, $, _, ko */

hqDefine('notifications/js/notifications_service.js', function () {
    'use strict';
    var module = {};
    var _private = {};
    _private.RMI = function () {
        console.log("RMI Method has not been set");
    };

    module.setRMI = function (rmiUrl, csrfToken) {
        var _rmi = RMI(rmiUrl, csrfToken);
        _private.RMI = function (remoteMethod, data) {
            return _rmi("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };
    };

    var Notification = function (data) {
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
            _private.RMI("mark_as_read", {id: self.id()});
            self.isRead(true);
            return true;
        };
    };

    var NotificationsServiceModel = function () {
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
            _private.RMI("get_notifications", {'did_it_work': true})
                .done(function (data) {
                    self.lastSeenNotificationDate(data.lastSeenNotificationDate);
                    _.each(data.notifications, function (data) {
                        self.notifications.push(new Notification(data));
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

            _private.RMI("save_last_seen", {"notification_id": self.notifications()[0].id()})
                .done(function(data) {
                    self.lastSeenNotificationDate(data.activated);
                })
                .fail(function(jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown); // eslint-disable-line no-console
                    self.hasError(true);
                });
        };
    };

    module.serviceModel = {};
    module.initService = function(notificationsKoSelector) {
        if ($(notificationsKoSelector).length < 1) {
            console.log("Cannot find notifications selector " + notificationsKoSelector);
            return;
        }
        module.serviceModel = new NotificationsServiceModel();
        module.serviceModel.init();
        $(notificationsKoSelector).koApplyBindings(module.serviceModel);
    };

    module.initUINotify = function (uiNotifySelector) {
        var uiNotifyAlerts = $(uiNotifySelector);
        if (uiNotifyAlerts.length > 0) {
            uiNotifyAlerts.on('closed.bs.alert', function () {
                var notifySlug = $(this).data('slug');
                _private.RMI("dismiss_ui_notify", {
                    "slug": notifySlug,
                });
            });
        }
    };

    return module;

});
