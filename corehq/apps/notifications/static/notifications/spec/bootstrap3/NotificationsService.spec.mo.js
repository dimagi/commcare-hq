describe('NotificationsService Unit Tests', function () {
    var fakeRMIUrl = '/fake/rmi',
        viewModel,
        FakePromise = function () {
            var self = this;
            self.successCallback = function () {};
            self.errorCallback = function () {};
            self.mock = function (options) {
                return {
                    done: function (callback) {
                        self.successCallback = callback;
                        return fakePromise.mock(options);
                    },
                    fail: function (errorCallback) {
                        self.errorCallback = errorCallback;
                        return fakePromise.mock(options);
                    },
                };
            };
        };

    var fakePromise = new FakePromise({});
    sinon.stub($, 'ajax', fakePromise.mock);

    it('Initialization', function () {
        var notifications = hqImport('notifications/js/bootstrap3/notifications_service');
        var csrfToken = $("#csrfTokenContainer").val();
        notifications.setRMI(fakeRMIUrl, csrfToken);
        notifications.initService('#js-settingsmenu-notifications');
        viewModel = notifications.serviceModel;
    });

    it("Model", function () {
        fakePromise.successCallback({
            hasUnread: true,
            notifications: [
                {
                    isRead: false,
                    content: "Test",
                    url: "#",
                    type: "info",
                    date: "Today",
                    activated: "2016-07-12T12:20:52.527",
                },
                {
                    isRead: true,
                    content: "Test 2",
                    url: "#",
                    type: "alert",
                    date: "Today",
                    activated: "2016-07-12T10:21:30.105",
                },
            ],
            lastSeenNotification: "2016-07-12T10:21:30.105",
        });
        assert.isTrue(viewModel.hasUnread());
        assert.isFalse(viewModel.seen());
        assert.equal(viewModel.notifications().length, 2);
        assert.isTrue(viewModel.notifications()[0].isInfo());
        assert.isFalse(viewModel.notifications()[0].isAlert());
        assert.isFalse(viewModel.notifications()[1].isInfo());
        assert.isTrue(viewModel.notifications()[1].isAlert());
        assert.isFalse(viewModel.hasError());

        fakePromise.successCallback({
            lastSeenNotificationDate: "2016-07-12T12:20:52.527",
        });
        viewModel.bellClickHandler();
        assert.isTrue(viewModel.seen());

        viewModel.notifications()[0].markAsRead();
        assert.isTrue(viewModel.notifications()[0].isRead());
        assert.isFalse(viewModel.hasUnread());
    });

    it("Error", function () {
        fakePromise.errorCallback({}, "", "fakeError");
        assert.isTrue(viewModel.hasError());
    });
});
