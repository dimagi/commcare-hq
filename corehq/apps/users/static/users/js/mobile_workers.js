/* global RMI */
hqDefine("users/js/mobile_workers", function () {
    var rmi = function () {};

    // TODO: rename to mobileWorkerModel for consistency
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

    // TODO: rename to mobileWorkersListModel for consistency
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

    // TODO: rename to something more specific
    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
        RETRIED: 'retried',
    };

    // TODO: rename worker / mobile worker to "user" everywhere?
    var mobileWorkerCreationModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, ['location_url', 'require_location_id']);

        var self = {};

        self.newMobileWorker = mobileWorker({
            user_id: '',
            first_name: 'my first name',
            last_name: 'my last name',
            username: 'me',
            password: '',
            is_active: true,
            location_id: '',
            creationStatus: STATUS.NEW,
        });

        self.newMobileWorkers = ko.observableArray();

        self.initializeMobileWorker = function () {
            // TODO: don't initialize select2 if this if this is a retry (the old code didn't)
            $("#id_location_id").select2({
                minimumInputLength: 0,
                width: '100%',
                placeholder: gettext("Select location"),
                allowClear: 1,
                ajax: {
                    delay: 100,
                    url: options.location_url,
                    data: function (params) {
                        return {
                            name: params.term,
                        };
                    },
                    dataType: 'json',
                    processResults: function (data) {
                        return {
                            results: _.map(data.results, function (r) {
                                return {
                                    text: r.name,
                                    id: r.id,
                                };
                            }),
                        };
                    },
                },
            });
        };

        self.allowSubmit = ko.computed(function () {
            var isValid = self.newMobileWorker.username() && self.newMobileWorker.password();
            if (options.require_location_id) {
                isValid = isValid && self.newMobileWorker.location_id();
            }
            // TODO: also require that usernameAvailabilityStatus === 'available'
            return isValid;
        });

        self.submitNewMobileWorker = function () {
            $("#newMobileWorkerModal").modal('hide');
            self.newMobileWorkers.push(self.newMobileWorker);
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
                    self.newMobileWorker.creationStatus(STATUS.WARNING);
                }
            })
            .fail(function () {
                self.newMobileWorker.creationStatus(STATUS.WARNING);
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

        var mobileWorkerCreation = mobileWorkerCreationModel({
            location_url: initialPageData.reverse('child_locations_for_select2'),
            require_location_id: !initialPageData.get('can_access_all_locations'),
        });
        $("#newMobileWorkerModalTrigger").koApplyBindings(mobileWorkerCreation);  // TODO: rename this id (casing)
        $("#newMobileWorkerModal").koApplyBindings(mobileWorkerCreation);  // TODO: rename this id (casing)
        $("#newMobileWorkersPanel").koApplyBindings(mobileWorkerCreation); // TODO: rename this id (casing)
    });
});
