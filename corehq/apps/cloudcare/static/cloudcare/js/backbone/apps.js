
if (typeof cloudCare === 'undefined') {
    var cloudCare = {};
}

cloudCare.dispatch = _.extend({}, Backbone.Events);

cloudCare.AppNavigation = Backbone.Router.extend({

    initialize: function() {
        // _.bindAll(this);
    },

    routes: {
        "view/:app":                        "app",
        "view/:app/:module":                "app:module",
        "view/:app/:module/:form":          "app:module:form",
        "view/:app/:module/:form/:case":    "app:module:form:case",
        "":                                 "clear"
    },

});


cloudCare.AppSummary = Backbone.Model.extend({
    idAttribute: "_id"
});

cloudCare.AppSummaryView = Selectable.extend({
    tagName: 'li',
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function() {
        $("<a />").text(this.model.get("name")).appendTo($(this.el));
        return this;
    }
});

cloudCare.AppList = Backbone.Collection.extend({
    model: cloudCare.AppSummary,
});

cloudCare.AppListView = Backbone.View.extend({
    el: $('#app-list'),

    initialize: function(){
        _.bindAll(this, 'render', 'appendItem', "getAppView", "clearSelectionState");
        this.appList = new cloudCare.AppList();
        this.appList.reset(this.options.apps);
        this._appViews = {};
        this.render();
    },

    render: function () {
        var self = this;
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
        $("<li />").addClass("nav-header").text("Apps").appendTo(ul);
        _(this.appList.models).each(function(item){
            self.appendItem(item);
        });
    },
    appendItem: function (item) {
        var self = this;
        var appView = new cloudCare.AppSummaryView({
            model: item
        });

        this._appViews[item.id] = appView;

        appView.on("selected", function () {
            if (self.selectedAppView) {
                self.selectedAppView.deselect();
            }
            if (self.selectedAppView !== this) {
                self.selectedAppView = this;
                cloudCare.dispatch.trigger("app:selected", this);
            }
        });
        appView.on("deselected", function () {
            self.selectedAppView = null;
            cloudCare.dispatch.trigger("app:deselected", this);
        });

        $('ul', this.el).append(appView.render().el);
    },
    getAppView: function (appId) {
        return this._appViews[appId];
    },

    clearSelectionState: function () {
        this.selectedAppView = null;
        _(_(this._appViews).values()).each(function (view) {
            view.deselect();
        });
    }
});

cloudCare.App = LocalizableModel.extend({
    idAttribute: "_id",
    initialize: function () {
        this.constructor.__super__.initialize.apply(this, [this.options]);
        _.bindAll(this, "updateModules", "urlRoot", "getSubmitId");
        var self = this;
        this.updateModules();
        this.on("change", function () {
            this.updateModules();
        });
    },
    urlRoot: function () {
        return this.get("urlRoot");
    },
    getSubmitId: function () {
        return this.get("copy_of") || this.id
    },
    updateModules: function () {
        var self = this;
        if (this.get("modules")) {
            var index = 0;
            this.modules = _(this.get("modules")).map(function (module) {
                var ret = new cloudCare.Module(module);
                ret.set("app_id", self.id);
                ret.set("submit_app_id", self.getSubmitId());
                ret.set("index", index);
                index++;
                return ret;
            });
        }
    }
});

cloudCare.Form = LocalizableModel.extend({
});

cloudCare.FormView = Selectable.extend({
    tagName: 'li',
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function () {
        $("<a />").text(this.model.getLocalized("name", this.options.language)).appendTo($(this.el));
        return this;
    }
});

cloudCare.Module = LocalizableModel.extend({
    initialize: function () {
        this.constructor.__super__.initialize.apply(this, [this.options]);
        _.bindAll(this, 'updateForms', 'getDetail');
        this.updateForms();
        this.on("change", function () {
            this.updateForms();
        });
    },

    getDetail: function (type) {
        return _(this.get("details")).find(function (elem) {
            return elem.type === type;
        });
    },

    updateForms: function () {
        var self = this, form;
        if (this.get("forms")) {
            var index = 0,
                sharedMeta = {
                    app_id: self.get('app_id'),
                    module_index: self.get('index'),
                    submit_app_id: self.get('submit_app_id')
                };

            this.forms = _(this.get("forms")).map(function (form) {
                form = new cloudCare.Form(form);
                form.set(sharedMeta);
                form.set({index: index});
                index++;
                return form;
            });
            // task-list
            if (self.get('task_list').show) {
                form = new cloudCare.Form({
                    name: self.get('task_list').label,
                    index: 'task-list',
                    requires: 'case'
                });
                form.set(sharedMeta);
                this.forms.push(form);
            }
            this.trigger("forms-changed");
        }
    },
    getFormByUniqueId: function (unique_id) {
        var self = this;
        for (var i = 0; i < self.forms.length; i ++) {
            var form = self.forms[i];
            if (form.get('unique_id') === unique_id) {
                return form;
            }
        }
        var exc = {
            type: 'FormLookupError',
            form_id: unique_id
        };
        throw exc;
    }
});

cloudCare.ModuleView = Selectable.extend({
    tagName: 'li',
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect');
    },
    render: function() {
        $("<a />").text(this.model.getLocalized("name", this.options.language)).appendTo($(this.el));
        return this;
    }
});

cloudCare.ModuleList = Backbone.Collection.extend({
    model: cloudCare.Module
});

cloudCare.ModuleListView = Backbone.View.extend({
    el: $('#module-list'),
    initialize: function () {
        _.bindAll(this, 'render', 'appendItem', 'updateModules', 'getModuleView', 'clearSelectionState');
        var self = this;
        this.moduleList = new cloudCare.ModuleList([], {
            language: this.options.language
        });
        this.moduleList.on("reset", function () {
            self.updateModules();
        });
        this.render();
    },
    render: function () {
        this.updateModules();
    },
    updateModules: function () {
        // clear
        $(this.el).html("");
        this._moduleViews = {};

        var self = this;
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
        $("<li />").addClass("nav-header").text("Modules").appendTo(ul);
        _(this.moduleList.models).each(function(item){
            self.appendItem(item);
        });
        self.trigger("modules:updated");
    },
    appendItem: function (item) {
        var self = this;
        var moduleView = new cloudCare.ModuleView({
            model: item,
            language: this.options.language

        });
        this._moduleViews[item.get("index")] = moduleView;

        moduleView.on("selected", function () {
            if (self.selectedModuleView) {
                self.selectedModuleView.deselect();
            }
            if (self.selectedModuleView !== this) {
                self.selectedModuleView = this;
                cloudCare.dispatch.trigger("module:selected", this.model);
            }
        });
        moduleView.on("deselected", function () {
            self.selectedModuleView = null;
            cloudCare.dispatch.trigger("module:deselected", this.model);
        });

        $('ul', this.el).append(moduleView.render().el);
    },
    getModuleView: function (moduleIndex) {
        return this._moduleViews[moduleIndex];
    },
    clearSelectionState: function () {
        this.selectedModuleView = null;
        _(_(this._moduleViews).values()).each(function (view) {
            view.deselect();
        });
    }
});

cloudCare.FormListView = Backbone.View.extend({
    el: $('#form-list'),
    initialize: function () {
        _.bindAll(this, 'render', 'appendForm', 'getFormView', 'clearSelectionState');
        this._formViews = {};
    },
    render: function () {
        var self = this;
        $(this.el).html("");
        if (this.model) {
	        var formUl = $("<ul />").addClass("nav nav-list").appendTo($(this.el));
	        $("<li />").addClass("nav-header").text("Forms").appendTo(formUl);
	        _(this.model.forms).each(function (form) {
	            self.appendForm(form);
	        });
        }
        return this;
    },
    appendForm: function (form) {
        var self = this;
        var formView = new cloudCare.FormView({
            model: form,
            language: this.options.language
        });
        this._formViews[form.get("index")] = formView;
        formView.on("selected", function () {
            if (self.selectedFormView) {
                self.selectedFormView.deselect();
            }
            if (self.selectedFormView !== this) {
                self.selectedFormView = this;
                cloudCare.dispatch.trigger("form:selected", this.model);
            }
        });
        formView.on("deselected", function () {
            self.selectedFormView = null;
            cloudCare.dispatch.trigger("form:deselected", this.model);
        });

	    $('ul', this.el).append(formView.render().el);
    },
    clearSelectionState: function () {
        this.selectedFormView = null;
        _(_(this._formViews).values()).each(function (view) {
            view.deselect();
        });
    },
    getFormView: function (formIndex) {
        return this._formViews[formIndex];
    }
});

cloudCare.AppView = Backbone.View.extend({

    initialize: function(){
        _.bindAll(this, 'render', 'setModel', 'showModule', "_clearCaseView",
                  "_clearFormPlayer", "_clearMainPane");
        var self = this;
        this.moduleListView = new cloudCare.ModuleListView({
            language: this.options.language
        });
        this.formListView = new cloudCare.FormListView({
            language: this.options.language
        });

        cloudCare.dispatch.on("form:selected", function (form) {
            self.selectForm(form);

        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.selectForm(null);
            // self.trigger("form:deselected", form);
        });
        cloudCare.dispatch.on("module:selected", function (module) {
            self.showModule(module);
        });
        cloudCare.dispatch.on("module:deselected", function (module) {
            self.showModule(null);

        });

        this.setModel(this.model);
    },
    setModel: function (app) {
        this.model = app;
    },
    showModule: function (module) {
        this._clearMainPane();
        this.formListView.model = module;
        this.formListView.render();
    },
    selectForm: function (form) {
        var self = this;
        var formListView = this.formListView;
        var selectedModule = this.formListView.model;

        self._clearFormPlayer();
        var playForm = function (url) {
            // go play the form. this is a little sketchy

            // clear current case information
            self._clearCaseView();

            var submitUrl = getSubmitUrl(self.options.submitUrlRoot, form.get("submit_app_id"));
            // get context
            resp = $.ajax({ url: url,
                            async: false,
                            dataType: "json" });
            resp.done(function (data) {
                data["onsubmit"] = function (xml) {
                    // post to receiver
                    $.ajax({
		                type: 'POST',
		                url: submitUrl,
		                data: xml,
		                success: function () {
		                    self._clearFormPlayer();
		                    self.showModule(selectedModule);
		                    showSuccess("Form successfully saved.", $("#cloudcare-main"), 2500);
		                }
		            });
		        };
		        data["onerror"] = function (resp) {
		            showError(resp.message, $("#cloudcare-main"));
		        };
		        var sess = new WebFormSession(data);
                // TODO: probably shouldn't hard code these divs
                sess.load($('#webforms'), $('#loading'), self.options.language);
            });
        };

        if (form) {
            var module = self.moduleListView.getModuleView(form.get('module_index')).model;
            function getUrl(form, caseModel) {
                var referencedForm = form, url;
                if (form.get('index') === 'task-list') {

                    referencedForm = module.getFormByUniqueId(caseModel.getProperty('form_id'));
                }
                url = getFormUrl(
                    self.options.urlRoot,
                    referencedForm.get("app_id"),
                    referencedForm.get("module_index"),
                    referencedForm.get("index")
                );
                if (caseModel !== undefined) {
                    url += "?case_id=" + caseModel.id;
                    if (form.get('index') === 'task-list') {
                        url += "&task-list=true";
                    }
                }
                return url;

            }

            if (form.get("requires") === "none") {
	            // no requirements, go ahead and play it
                playForm(getUrl(form));
            } else if (form.get("requires") === "case") {
	            var listDetails = formListView.model.getDetail("case_short");
	            var summaryDetails = formListView.model.getDetail("case_long");
	            // clear anything existing
	            self._clearCaseView();
	            formListView.caseView = new cloudCare.CaseMainView({
	                el: $("#cases"),
	                listDetails: listDetails,
	                summaryDetails: summaryDetails,
	                appConfig: {
                        app_id: form.get("app_id"),
	                    module_index: form.get("module_index"),
                        form_index: form.get("index"),
                        module: module
                    },
	                language: formListView.options.language,
	                caseUrl: getCaseFilterUrl(
                        self.options.caseUrlRoot,
                        form.get("app_id"),
                        form.get("module_index"),
                        // index is passed in so that if it's equal to 'task-list' that'll be taken into account
                        // otherwise it's ignored
                        form.get('index')
                    )
	            });
	            cloudCare.dispatch.on("case:selected", function (caseModel) {
	                formListView.enterForm = $("<a />").text("Enter " + form.getLocalized("name", self.options.language)).addClass("btn btn-primary").appendTo(
	                        $(formListView.caseView.detailsView.el));
	                formListView.enterForm.click(function () {

	                    playForm(getUrl(form, caseModel));
	                });
	            });
	            cloudCare.dispatch.on("case:deselected", function (caseModel) {
	                if (formListView.enterForm) {
	                    formListView.enterForm.detach();
	                    formListView.enterForm = null;
	                }
	            });

	            formListView.caseView.listView.caseList.on("reset", function () {
	                cloudCare.dispatch.trigger("cases:updated");
	            });
	        }
        } else {
            if (formListView.caseView) {
                $(formListView.caseView.el).html("");
            }
        }
    },
    render: function () {
        // clear details when rerendering
        this.showModule(null);
        if (!this.model) {
            this.moduleListView.moduleList.reset([]);
        } else {
            this.moduleListView.moduleList.reset(this.model.modules);
        }
        return this;
    },
    _clearMainPane: function () {
        this._clearCaseView();
        this._clearFormPlayer();
    },
    _clearCaseView: function () {
        if (this.formListView.caseView) {
            $(this.formListView.caseView.el).remove().html("");
        }
    },
    _clearFormPlayer: function () {
        // TODO: clean hack/hard coded id
        $('#webforms').html("");
    }
});

cloudCare.AppMainView = Backbone.View.extend({
    el: $('#app-main'),

    initialize: function () {
        _.bindAll(this, 'render', 'selectApp', "clearCases", "clearForms", "clearModules", "clearAll", "navigate");
        var self = this;

        this._selectedModule = null;
        this._selectedForm = null;
        this._selectedCase = null;
        this._navEnabled = true;
        this.router = new cloudCare.AppNavigation();
        this.appListView = new cloudCare.AppListView({
            apps: this.options.apps,
            language: this.options.language
        });
        cloudCare.dispatch.on("app:selected", function (app) {
            self.navigate("view/" + app.model.id);
            self.selectApp(app.model.id);
        });
        cloudCare.dispatch.on("app:deselected", function (app) {
            this._selectedModule = null;
            self.navigate("");
            self.selectApp(null);
        });
        this.appView = new cloudCare.AppView({
            // if you pass in model: it will auto-populate the view
            model: this.options.model,
            language: this.options.language,
            caseUrlRoot: this.options.caseUrlRoot,
            urlRoot: this.options.urlRoot,
            submitUrlRoot: this.options.submitUrlRoot
        });

        // utilities
        var selectApp = function (appId) {
            self.appListView.getAppView(appId).select();
        };

        var selectModule = function (moduleIndex) {
            var modView = self.appView.moduleListView.getModuleView(moduleIndex);
            if (modView) {
                modView.select();
            }
            // other event handling magic uses this to select the module
            // after it gets loaded.
            self._selectedModule = moduleIndex;
        };

        var selectForm = function (formIndex) {
            var formView = self.appView.formListView.getFormView(formIndex);
            if (formView) {
                formView.select();
            }
            self._selectedForm = formIndex;
        };

        var selectCase = function (caseId) {
            var caseMainView = self.appView.formListView.caseView;
            if (caseMainView) {
                var caseView = caseMainView.listView.caseMap[caseId];
                if (caseView) {
                    caseView.select();
                }
            }
            self._selectedCase = caseId;
        };

        var pauseNav = function (f) {
            // wrapper to prevent navigation during the execution
            // of a function
            var wrappedF = function () {
                try {
                    self._navEnabled = false;
                    return f.apply(this, arguments);
                } finally {
                    self._navEnabled = true;
                }
            };
            return wrappedF;
        };

        // incoming routes

        this.router.on("route:clear", pauseNav(function () {
            self.clearAll();
        }));

        var _stripParams = function (val) {
            if (val.indexOf("?") !== -1) {
                return val.substring(0, val.indexOf("?"));
            }
            return val;
        }
        this.router.on("route:app", pauseNav(function (appId) {
            self.clearModules();
            selectApp(_stripParams(appId));
        }));

        this.router.on("route:app:module", pauseNav(function (appId, moduleIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(_stripParams(moduleIndex));
        }));
        this.router.on("route:app:module:form", pauseNav(function (appId, moduleIndex, formIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(_stripParams(formIndex));
        }));
        this.router.on("route:app:module:form:case", pauseNav(function (appId, moduleIndex, formIndex, caseId) {
            self.clearCases();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex);
            selectCase(_stripParams(caseId));
        }));

        // these are also incoming routes, that look funny because of how the event
        // spaghetti resolves.
        this.appView.moduleListView.on("modules:updated", pauseNav(function () {
            // this selects an appropriate module any time they are updated.
            // we have to be careful to clear this field anytime a module
            // is deselected
            if (self._selectedModule !== null) {
                this.getModuleView(self._selectedModule).select();
            }
            self._selectedModule = null;
        }));
        cloudCare.dispatch.on("cases:updated", pauseNav(function () {
            // same trick but with cases
            if (self._selectedCase !== null) {
                self.appView.formListView.caseView.listView.caseMap[self._selectedCase].select();
            }
            self._selectedCase = null;
        }));


        // setting routes
        cloudCare.dispatch.on("module:selected", function (module) {
            self.navigate("view/" + module.get("app_id") +
                                 "/" + module.get("index"));
            // hack to resolve annoying event-driven dependencies (see below)
            self.trigger("module:selected");
        });
        self.on("module:selected", function () {
            // magic pairing with the above to support proper selection ordering
            if (self._selectedForm !== null) {
                self.appView.formListView.getFormView(self._selectedForm).select();
            }
            self._selectedForm = null;
        });

        cloudCare.dispatch.on("module:deselected", function (module) {
            self.navigate("view/" + module.get("app_id"));
            self.clearModules();
        });
        cloudCare.dispatch.on("form:selected", function (form) {
            self.navigate("view/" + form.get("app_id") +
                                 "/" + form.get("module_index") +
                                 "/" + form.get("index"));

        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.navigate("view/" + form.get("app_id") +
                                 "/" + form.get("module_index"));
            self.clearForms();
        });
        cloudCare.dispatch.on("case:selected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            self.navigate("view/" + appConfig.app_id +
                                 "/" + appConfig.module_index +
                                 "/" + appConfig.form_index +
                                 "/" + caseModel.id);
        });
        cloudCare.dispatch.on("case:deselected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            self.navigate("view/" + appConfig.app_id +
                                 "/" + appConfig.module_index +
                                 "/" + appConfig.form_index);
        });


    },

    navigate: function (path) {
        if (this._navEnabled) {
            this.router.navigate(path);
        }
    },

    selectApp: function (appId) {
        var self = this;
        if (appId === null) {
            this.clearAll();

        }
        else {
            this.app = new cloudCare.App({
	            _id: appId,
	        });
	        this.app.set("urlRoot", this.options.appUrlRoot);
	        showLoading();
	        this.app.fetch({
	            success: function (model, response) {
	                self.appView.setModel(model);
	                self.appView.render();
	                hideLoading();
	            }
	        });
	    }
    },
    clearCases: function () {
        // TODO
        this._selectedCase = null;

    },
    clearForms: function () {
        this.clearCases();
        this._selectedForm = null;
        this.appView.formListView.clearSelectionState();
        this.appView.selectForm(null);
    },
    clearModules: function () {
        this.clearForms();
        this._selectedModule = null;
        this.appView.moduleListView.clearSelectionState();
        this.appView.showModule(null);
    },
    clearAll: function () {
        this.clearModules();
        this.appListView.clearSelectionState();
        this.app = null;
        this.appView.setModel(null);
        this.appView.render();
    },

    render: function () {
        return this;
    }
});
