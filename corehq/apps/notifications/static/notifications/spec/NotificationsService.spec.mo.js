describe('NotificationsService Unit Tests', function() {
    var fakeRMIUrl = '/fake/rmi',
        viewModel,
        FakePromise = function (options) {
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
                    }
                };
            };
        };

    var fakePromise = new FakePromise({});
    sinon.stub(jQuery, 'ajax', fakePromise.mock);

    it('Initialization', function () {
        viewModel = $('#js-settingsmenu-notifications').startNotificationsService(fakeRMIUrl);
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
                    date: "Today"
                },
                {
                    isRead: true,
                    content: "Test 2",
                    url: "#",
                    type: "alert",
                    date: "Today"
                }
            ]
        });
        assert.isTrue(viewModel.hasUnread());
        assert.equal(viewModel.notifications().length, 2);
        assert.isTrue(viewModel.notifications()[0].isInfo());
        assert.isFalse(viewModel.notifications()[0].isAlert());
        assert.isFalse(viewModel.notifications()[1].isInfo());
        assert.isTrue(viewModel.notifications()[1].isAlert());
        assert.isFalse(viewModel.hasError());
    });

    it("Error", function () {
        fakePromise.errorCallback({}, "", "fakeError");
        assert.isTrue(viewModel.hasError());
    });
});
