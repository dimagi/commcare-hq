describe("DrilldownToFormController - Initialization", function () {
    AppDrill.prepareTests();

    it('Basic Form init', function () {
        var response = AppDrill.getSingleAppResponse();

        AppDrill.$httpBackend
            .when('POST', AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES)
            .respond(response);
        AppDrill.$httpBackend.expectPOST(AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES);
        var controller = AppDrill.createController();
        assert.isFalse(AppDrill.currentScope.isLoaded);
        AppDrill.$httpBackend.flush();

        // make sure internal variables are properly set on init
        assert.deepEqual(controller._placeholders, response.placeholders);
        assert.deepEqual(controller._app_types, response.app_types);
        assert.deepEqual(controller._apps_by_type, response.apps_by_type);
        assert.deepEqual(controller._modules_by_app, response.modules_by_app);
        assert.deepEqual(controller._forms_by_app_by_module, response.forms_by_app_by_module);
        assert.deepEqual(controller._case_types_by_app, {});

        assert.isFalse(AppDrill.currentScope.hasSpecialAppTypes);
        assert.isTrue(AppDrill.currentScope.isLoaded);
        assert.isNull(AppDrill.currentScope.formLoadError);

        // Make sure that Select2s have access to the correct variables
        assert.equal(controller._select2Test.app_type.data.length, 1);
        assert.equal(controller._select2Test.app_type.defaults, 'all');
        assert.isNull(controller._select2Test.app_type.placeholder);
        assert.equal(controller._select2Test.application.data.length, 1);
        assert.equal(controller._select2Test.application.defaults, '');
        assert.equal(
            controller._select2Test.application.placeholder,
            response.placeholders.application
        );
        assert.isUndefined(controller._select2Test.module.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.equal(
            controller._select2Test.module.placeholder,
            response.placeholders.module
        );
        assert.isUndefined(controller._select2Test.form.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.equal(
            controller._select2Test.form.placeholder,
            response.placeholders.form
        );
        assert.isUndefined(controller._select2Test.case_type.data);
        assert.equal(controller._select2Test.case_type.defaults, '');
        assert.isUndefined(controller._select2Test.case_type.placeholder);
    });

    it('Multiple App Types init', function () {
        var response = AppDrill.getMultiAppTypesResponse();
        AppDrill.$httpBackend
            .when('POST', AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES)
            .respond(response);
        AppDrill.$httpBackend.expectPOST(AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES);
        var controller = AppDrill.createController();
        assert.isFalse(AppDrill.currentScope.isLoaded);
        AppDrill.$httpBackend.flush();

        // make sure internal variables are properly set on init
        assert.deepEqual(controller._placeholders, response.placeholders);
        assert.deepEqual(controller._app_types, response.app_types);
        assert.deepEqual(controller._apps_by_type, response.apps_by_type);
        assert.deepEqual(controller._modules_by_app, response.modules_by_app);
        assert.deepEqual(controller._forms_by_app_by_module, response.forms_by_app_by_module);
        assert.deepEqual(controller._case_types_by_app, {});

        assert.isTrue(AppDrill.currentScope.hasSpecialAppTypes);
        assert.isTrue(AppDrill.currentScope.isLoaded);
        assert.isNull(AppDrill.currentScope.formLoadError);

        // Make sure that Select2s have access to the correct variables
        assert.equal(controller._select2Test.app_type.data.length, 4);
        assert.equal(controller._select2Test.app_type.defaults, 'all');
        assert.isNull(controller._select2Test.app_type.placeholder);
        assert.equal(controller._select2Test.application.data.length, 1);
        assert.equal(controller._select2Test.application.defaults, '');
        assert.equal(
            controller._select2Test.application.placeholder,
            response.placeholders.application
        );
        assert.isUndefined(controller._select2Test.module.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.equal(
            controller._select2Test.module.placeholder,
            response.placeholders.module
        );
        assert.isUndefined(controller._select2Test.form.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.equal(
            controller._select2Test.form.placeholder,
            response.placeholders.form
        );
        assert.isUndefined(controller._select2Test.case_type.data);
        assert.equal(controller._select2Test.case_type.defaults, '');
        assert.isUndefined(controller._select2Test.case_type.placeholder);
    });


    it('Case Types init', function () {
        var response = AppDrill.getCaseTypeResponse();
        AppDrill.$httpBackend
            .when('POST', AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES)
            .respond(response);
        AppDrill.$httpBackend.expectPOST(AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES);
        var controller = AppDrill.createController();
        assert.isFalse(AppDrill.currentScope.isLoaded);
        AppDrill.$httpBackend.flush();

        // make sure internal variables are properly set on init
        assert.deepEqual(controller._placeholders, response.placeholders);
        assert.deepEqual(controller._app_types, response.app_types);
        assert.deepEqual(controller._apps_by_type, response.apps_by_type);
        assert.deepEqual(controller._modules_by_app, {});
        assert.deepEqual(controller._forms_by_app_by_module, {});
        assert.deepEqual(controller._case_types_by_app, response.case_types_by_app);

        assert.isTrue(AppDrill.currentScope.hasSpecialAppTypes);
        assert.isTrue(AppDrill.currentScope.isLoaded);
        assert.isNull(AppDrill.currentScope.formLoadError);

        // Make sure that Select2s have access to the correct variables
        assert.equal(controller._select2Test.app_type.data.length, 3);
        assert.equal(controller._select2Test.app_type.defaults, 'all');
        assert.isNull(controller._select2Test.app_type.placeholder);
        assert.equal(controller._select2Test.application.data.length, 1);
        assert.equal(controller._select2Test.application.defaults, '');
        assert.equal(
            controller._select2Test.application.placeholder,
            response.placeholders.application
        );
        assert.isUndefined(controller._select2Test.module.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.isUndefined(controller._select2Test.module.placeholder);
        assert.isUndefined(controller._select2Test.form.data);
        assert.equal(controller._select2Test.module.defaults, '');
        assert.isUndefined(controller._select2Test.form.placeholder);
        assert.isUndefined(controller._select2Test.case_type.data);
        assert.equal(controller._select2Test.case_type.defaults, '');
        assert.equal(
            controller._select2Test.case_type.placeholder,
            response.placeholders.case_type
        );
    });

    it('registers server error', function () {
        var errorMsg = 'test server error';
        AppDrill.$httpBackend
            .when('POST', AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES)
            .respond({error: errorMsg});
        AppDrill.createController();
        assert.isFalse(AppDrill.currentScope.isLoaded);
        AppDrill.$httpBackend.flush();
        assert.equal(AppDrill.currentScope.formLoadError, errorMsg);
        assert.isTrue(AppDrill.currentScope.isLoaded);
    });

    it('registers HTTP error', function () {
        AppDrill.$httpBackend
            .when('POST', AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES)
            .respond(500);
        AppDrill.createController();
        assert.isFalse(AppDrill.currentScope.isLoaded);
        AppDrill.$httpBackend.flush();
        assert.equal(AppDrill.currentScope.formLoadError, 'default');
        assert.isTrue(AppDrill.currentScope.isLoaded);
    });
});
