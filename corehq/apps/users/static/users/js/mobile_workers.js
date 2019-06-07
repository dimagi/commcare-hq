/* global RMI */
hqDefine("users/js/mobile_workers", function () {
    var rmi = function () {};

    var mobileWorker = function (options) {
        var self = ko.mapping.fromJS(options);

        self.action_error = ko.observable('');

        self.editUrl = ko.computed(function () {
            return hqImport("hqwebapp/js/initial_page_data").reverse('edit_commcare_user', self.user_id());
        });

        self.is_active.subscribe(function (newValue) {
            var urlName = newValue ? 'activate_commcare_user' : 'deactivate_commcare_user',
                $modal = $('#' + (newValue ? 'activate_' : 'deactivate_') + self.user_id());

            $modal.find(".btn").addSpinnerToButton();
            $.ajax({
                method: 'POST',
                url: hqImport("hqwebapp/js/initial_page_data").reverse(urlName, self.user_id()),
                success: function (data) {
                    $modal.modal('hide');
                    if (data.success) {
                        self.action_error('');
                    } else {
                        self.action_error(data.error);
                    }
                },
                error: function () {
                    $modal.modal('hide');
                    self.action_error(gettext("Issue communicating with server. Try again."));
                },
            });
        });

        return self;
    };

    var mobileWorkersList = function () {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');
        self.deactivatedOnly = ko.observable(false);

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable();

        // Visibility of spinners, messages, and user table
        self.hasError = ko.observable(false);
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.projectHasUsers = ko.observable(true);

        self.showProjectHasNoUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.projectHasUsers();
        });

        self.showNoUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.totalItems() && !self.showProjectHasNoUsers();
        });

        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError() && !self.showNoUsers() && !self.showProjectHasNoUsers();
        });

        self.deactivatedOnly.subscribe(function () {
            self.goToPage(1);
        });

        self.goToPage = function (page) {
            self.users.removeAll();
            self.hasError(false);
            self.showPaginationSpinner(true);
            $.ajax({
                method: 'GET',
                url: hqImport("hqwebapp/js/initial_page_data").reverse('paginate_mobile_workers'),
                data: {
                    page: page || 1,
                    query: self.query(),
                    limit: self.itemsPerPage(),
                    showDeactivatedUsers: self.deactivatedOnly(),
                },
                success: function (data) {
                    self.totalItems(data.total);
                    self.users(_.map(data.users, function (user) {
                        return mobileWorker(user);
                    }));

                    if (!self.query()) {
                        self.projectHasUsers(!!data.users.length);
                    }
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(false);
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(true);
                },
            });
        };
        self.goToPage(1);
        return self;
    };

    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
        RETRIED: 'retried',
    };


    var mobileWorkerCreation = function () {
        var self = {};

        self.newMobileWorker = mobileWorker({
            user_id: '',
            first_name: 'my first name',
            last_name: 'my last name',
            username: 'me',
            password: '',
            is_active: true,
            location_id: '24b6c9c47ab046b0885fdd9e6d0dca67',
            creationStatus: STATUS.NEW,
        });

        self.initializeMobileWorker = function () {
            console.log("do something");
        };

        self.submitNewMobileWorker = function () {
            $("#newMobileWorkerModal").modal('hide');
            //$scope.workers.push($scope.mobileWorker); // TODO: panel of new workers
            self.newMobileWorker.creationStatus(STATUS.PENDING);
            if (hqImport("hqwebapp/js/initial_page_data").get("implement_password_obfuscation")) {
                // TODO: draconian password requirements
                //newWorker.password = (hqImport("nic_compliance/js/encoder")()).encode(newWorker.password);
            }
            rmi('create_mobile_worker', {
                mobileWorker: ko.mapping.toJS(self.newMobileWorker),
            })
            .done(function (data) {
                if (data.success) {
                    ko.mapping.fromJS({
                        user_id: data.user_id,
                    }, self.newMobileWorker);
                    self.newMobileWorker.creationStatus(STATUS.SUCCESS);
                } else {
                    // TODO
                    /*newWorker.creationStatus = STATUS.WARNING;
                    deferred.reject(data);*/
                }
            })
            .fail(function () {
                // TODO
                /*newWorker.creationStatus = STATUS.WARNING;
                deferred.reject(
                    gettext("Sorry, there was an issue communicating with the server.")
                );*/
            });
        };

        return self;
    };

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            rmiInvoker = RMI(initialPageData.reverse('mobile_workers'), $("#csrfTokenContainer").val());
        rmi = function (remoteMethod, data) {
            return rmiInvoker("", data, {headers: {"DjNg-Remote-Method": remoteMethod}});
        };

        $("#mobile-workers-list").koApplyBindings(mobileWorkersList());
        $("#newMobileWorkerModal").koApplyBindings(mobileWorkerCreation());
    });
});
