/**
 * NotificationsService communicates with the NotificationsServiceRMIView django view
 * to fetch and update notifications for users on CommCare HQ.
 *
 */

hqDefine('notifications/js/bootstrap3/notifications_service', [
    'jquery',
    'knockout',
    'underscore',
    'jquery.rmi/jquery.rmi',
    'analytix/js/kissmetrix',
    'hqwebapp/js/bootstrap3/hq.helpers',
], function (
    $,
    ko,
    _,
    RMI,
    kissmetrics
) {
    'use strict';

    // Workaround for non-RequireJS pages: when `define` doesn't exist, RMI is just a global variable.
    RMI = RMI || window.RMI;

    var module = {};
    var _private = {};
    _private.RMI = function () {};

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
        self.isFeature = ko.computed(function () {
            return self.type() === 'feat_basic' || self.type() === 'feat_pro';
        });
        self.markAsRead = function () {
            _private.RMI("mark_as_read", {id: self.id()})
                .done(function (data) {
                    if (self.isFeature()) {
                        kissmetrics.track.event("Notifications tab - Clicked notifications tab - " +
                            "Clicked on Case Sharing text link",
                            {email: data.email, domain: data.domain});
                    }
                });
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
            return _.some(self.notifications(), function (note) {
                return !note.isRead();
            });
        });

        self.hasUnreadFeatureNotification = ko.computed(function () {
            return _.some(self.notifications(), function (note) {
                return !note.isRead() && (note.type() === 'feat_basic' || note.type() === 'feat_pro')
            });
        })

        self.seen = ko.computed(function () {
            if (self.hasUnreadFeatureNotification()) {
                return false;
            }

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
                    self.hasError(true);
                });
        };

        self.bellClickHandler = function () {
            if (self.notifications().length === 0) {
                return;
            }

            _private.RMI("save_last_seen", {"notification_id": self.notifications()[0].id()})
                .done(function (data) {
                    self.lastSeenNotificationDate(data.activated);
                    if (self.hasUnreadFeatureNotification()) {
                        kissmetrics.track.event("Notifications tab - Clicked notifications tab",
                            {email: data.email, domain: data.domain});
                    }
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    console.log(errorThrown); // eslint-disable-line no-console
                    self.hasError(true);
                });
        };
    };

    module.serviceModel = {};
    module.initService = function (notificationsKoSelector) {
        if ($(notificationsKoSelector).length < 1) {
            return;
        }
        module.serviceModel = new NotificationsServiceModel();
        module.serviceModel.init();
        if (!ko.dataFor($(notificationsKoSelector)[0])) {
            // avoid multiple inits
            $(notificationsKoSelector).koApplyBindings(module.serviceModel);
        }
    };

    module.relativelyPositionUINotify = function (uiNotifySelector) {
        var uiNotifyAlerts = $(uiNotifySelector);
        _.each(uiNotifyAlerts, function (elem) {
            var $notify = $(elem),
                $target = $($notify.data('target'));

            $notify.remove();
            $target
                .css('position', 'relative')
                .append($notify);

        });
    };

    // Store dismissed slugs client-side so that alerts that are generated client-side
    // don't get re-created after user has dismissed them.
    var dismissedSlugs = [];
    module.initUINotify = function (uiNotifySelector) {
        var uiNotifyAlerts = $(uiNotifySelector);
        if (uiNotifyAlerts.length > 0) {
            uiNotifyAlerts.on('closed.bs.alert', function () {
                var notifySlug = $(this).data('slug');
                dismissedSlugs.push(notifySlug);
                _private.RMI("dismiss_ui_notify", {
                    "slug": notifySlug,
                });
            });
            uiNotifyAlerts.each(function () {
                if (_.contains(dismissedSlugs, $(this).data('slug'))) {
                    $(this).addClass("hide");
                }
            });
        }
    };

    return module;
});
