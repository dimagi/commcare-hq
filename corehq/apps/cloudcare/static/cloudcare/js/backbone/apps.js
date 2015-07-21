
if (typeof cloudCare === 'undefined') {
    var cloudCare = {};
}

cloudCare.dispatch = _.extend({}, Backbone.Events);

cloudCare.AppNavigation = Backbone.Router.extend({

    initialize: function() {
        _.bindAll(this, 'setView');
    },
    routes: {
        // NOTE: if you edit these, you should also look at the views.py file
        "view/:app":                                        "app",
        "view/:app/:module":                                "app:module",
        "view/:app/:module/:form":                          "app:module:form",
        "view/:app/:module/:form/enter/":                   "app:module:form:enter",
        "view/:app/:module/:form/case/:case":               "app:module:form:case",
        "view/:app/:module/:form/parent/:parent":           "app:module:form:parent",
        "view/:app/:module/:form/parent/:parent/case/:case":"app:module:form:parent:case",
        "view/:app/:module/:form/case/:case/enter/":        "app:module:form:case:enter",
        "":                                                 "clear"
    },
    setView: function (view) {
        this.view = view;
    }
});


cloudCare.AppSummary = Backbone.Model.extend({
    idAttribute: "_id"
});

cloudCare.AppSummaryView = Selectable.extend({
    tagName: 'li',
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect', 'enable', 'disable');
    },
    render: function() {
        $("<a />").text(this.model.get("name")).appendTo($(this.el));
        return this;
    }
});

cloudCare.AppList = Backbone.Collection.extend({
    model: cloudCare.AppSummary
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
        var ul = $("<ul />").addClass("nav nav-list").appendTo($(self.el));
        $("<li />").addClass("nav-header").text("Apps").appendTo(ul);
        _(self.appList.models).each(function(item){
            self.appendItem(item);
        });
    },
    appendItem: function (item) {
        var self = this;
        var appView = new cloudCare.AppSummaryView({
            model: item
        });

        self._appViews[item.id] = appView;

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
        var self = this;
        self.constructor.__super__.initialize.apply(self, [self.options]);
        _.bindAll(self, "updateModules", "url", "urlRoot", "getSubmitUrl");

        self.updateModules();
        self.on("change", function () {
            this.updateModules();
        });
    },
    url: function () {
        // HT: http://stackoverflow.com/questions/10555962/enable-django-and-tastypie-support-for-trailing-slashes
        var original_url = Backbone.Model.prototype.url.call( this );
        var parsed_url = original_url + ( original_url.charAt( original_url.length - 1 ) == '/' ? '' : '/' );
        return parsed_url;
    },
    urlRoot: function () {
        return this.get("urlRoot");
    },
    getSubmitUrl: function () {
        return this.get('post_url');
    },
    renderFormRoot: function () {
        return this.get("renderFormRoot");
    },
    instanceViewerEnabled: function () {
        return this.get("instanceViewerEnabled");
    },
    updateModules: function () {
        var self = this;
        if (self.get("modules")) {
            var index = 0;
            self.modules = _(self.get("modules")).map(function (module) {
                var ret = new cloudCare.Module(module);
                ret.set("app_id", self.id);
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
        var self = this;
        _.bindAll(self, 'render', 'toggle', 'select', 'deselect', 'enable', 'disable');
        cloudCare.dispatch.on("form:enter", function (form, caseModel) {
            self.disable();
        });
        cloudCare.dispatch.on("form:ready form:error", function (form, caseModel) {
            self.enable();
        });
    },
    render: function () {
        $("<a />").text(this.model.getLocalized("name", this.options.language)).appendTo($(this.el));
        return this;
    }
});

cloudCare.FormSession = Backbone.Model.extend({
    initialize: function() {
        _.bindAll(this, "url");
    },
    url: function () {
        // HT: http://stackoverflow.com/questions/10555962/enable-django-and-tastypie-support-for-trailing-slashes
        var original_url = Backbone.Model.prototype.url.call( this );
        var parsed_url = original_url + ( original_url.charAt( original_url.length - 1 ) == '/' ? '' : '/' );
        return parsed_url;
    }
});

cloudCare.SessionView = Selectable.extend({
    tagName: 'li',
    initialize: function() {
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect', 'enable', 'disable');
    },
    render: function() {
        var self = this;
        var deleteEl = $("<a />").addClass("close").text("x");
        deleteEl.appendTo($(this.el));
        deleteEl.click(function (e) {
            e.stopPropagation();
            var dialog = confirm(translatedStrings.deleteSaved);
            if (dialog == true) {
                self.model.destroy();
                showSuccess(translatedStrings.deleteSuccess, $("#cloudcare-notifications"), 10000);
            }
        });
        $("<a />").text(this.model.get('display')).appendTo($(this.el));
        return this;
    }
});

cloudCare.SessionList = Backbone.Collection.extend({
    initialize: function () {
        var self = this;
        _.bindAll(self, 'url', 'setUrl');
        self.casedb = {};
    },
    model: cloudCare.FormSession,
    url: function () {
        return this.sessionUrl;
    },
    setUrl: function (url) {
        this.sessionUrl = url;
    }
});

cloudCare.SessionListView = Backbone.View.extend({
    el: $('#sessions'),
    initialize: function(){
        var self = this;
        _.bindAll(self, 'render', 'appendItem', 'reset');
        self.sessionList = new cloudCare.SessionList();
        self.sessionList.setUrl(self.options.sessionUrl);
        self._selectedSessionView = null;
        self.reset();
        self.sessionList.on('remove', function () {
                self.render()
            }
        )
    },
    reset: function () {
        var self = this;
        self.sessionList.reset();
        self.sessionList.fetch({
            success: function (collection, response) {
                self.render();
            }
        });
    },
    render: function () {
        var self = this;
        $(self.el).html('');
        if (self.sessionList.length) {
            var ul = $("<ul />").addClass("nav nav-list").appendTo($(self.el));
            $("<li />").addClass("nav-header").text("Incomplete Forms").appendTo(ul);
            _(self.sessionList.models).each(function(item){
                self.appendItem(item);
            });
        }
    },
    appendItem: function (item) {
        var self = this;
        var sessionView = new cloudCare.SessionView({
            model: item
        });
        sessionView.on("selected", function () {
            if (self._selectedSessionView) {
                self._selectedSessionView.deselect();
            }
            self._selectedSessionView = this;
            cloudCare.dispatch.trigger("session:selected", this.model);

        });
        sessionView.on("deselected", function () {
            self._selectedSessionView = null;
            cloudCare.dispatch.trigger("session:deselected", this.model);

        });
        $('ul', this.el).append(sessionView.render().el);
    }
});


cloudCare.Module = LocalizableModel.extend({
    initialize: function () {
        this.constructor.__super__.initialize.apply(this, [this.options]);
        _.bindAll(this, 'updateForms');
        this.updateForms();
        this.on("change", function () {
            this.updateForms();
        });
    },

    updateForms: function () {
        var self = this, form;
        if (self.get("forms")) {
            var index = 0,
                sharedMeta = {
                    app_id: self.get('app_id'),
                    module_index: self.get('index')
                };

            self.forms = _(self.get("forms")).map(function (form) {
                form = new cloudCare.Form(form);
                form.set(sharedMeta);
                form.set({index: index});
                index++;
                return form;
            });
            // task-list
            if (self.get('task_list') && self.get('task_list').show) {
                form = new cloudCare.Form({
                    name: self.get('task_list').label,
                    index: 'task-list',
                    requires: 'case'
                });
                form.set(sharedMeta);
                self.forms.push(form);
                self.taskListOnly = true;
            }
            self.trigger("forms-changed");
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
        _.bindAll(this, 'render', 'toggle', 'select', 'deselect', 'enable', 'disable');
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
            language: self.options.language

        });
        self._moduleViews[item.get("index")] = moduleView;

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

        $('ul', self.el).append(moduleView.render().el);
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
        var taskListOnly = self.model ? self.model.taskListOnly : false;
        $(self.el).html("");
        if (self.model) {
	        var formUl = $("<ul />").addClass("nav nav-list").appendTo($(self.el));
	        $("<li />").addClass("nav-header").text("Forms").appendTo(formUl);
	        _(self.model.forms).each(function (form) {
                if (!taskListOnly || form.get('index') === 'task-list') {
                    self.appendForm(form);
                }
	        });
        }
        return self;
    },
    appendForm: function (form) {
        var self = this;
        var formView = new cloudCare.FormView({
            model: form,
            language: self.options.language
        });
        self._formViews[form.get("index")] = formView;
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

	    $('ul', self.el).append(formView.render().el);
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
        var self = this;
        _.bindAll(self, 'render', 'setModel', 'showModule', "_clearCaseView",
                  "_clearFormPlayer", "_clearMainPane", "selectParent");
        window.appView = self;
        self.moduleListView = new cloudCare.ModuleListView({
            language: self.options.language
        });
        self.formListView = new cloudCare.FormListView({
            language: self.options.language
        });
        self.caseSelectionView = new cloudCare.CaseSelectionView({
            language: self.options.language
        });

        cloudCare.dispatch.on("form:selected", function (form) {
            if (self.selectedForm !== form){
                self.selectParent(null);
            }
            self.selectForm(form);
        });
        cloudCare.dispatch.on("parent:selected", function (parent) {
            self.selectParent(parent);
            self.selectForm(self.selectedForm);
        });
        cloudCare.dispatch.on("session:deselected", function (session) {
            self._clearFormPlayer();
        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.selectForm(null);
            self.selectParent(null);
            // self.trigger("form:deselected", form);
        });
        cloudCare.dispatch.on("module:selected", function (module) {
            self.showModule(module);
        });
        cloudCare.dispatch.on("module:deselected", function (module) {
            self.showModule(null);
        });

        self.setModel(self.model);
        self.selectedModule = null;
        self.selectedForm = null;
        self.selectedParent = null;
    },
    setModel: function (app) {

        this.model = app;
    },
    selectCase: function (caseModel) {
        var self = this;
        self.formListView.caseView.selectCase(caseModel);
        if (caseModel) {
            var module = self.selectedModule;
            var form = self.selectedForm;

            if (caseModel.get("properties").case_type === self.selectedModule.get("case_type")) {
                // Construct a button which will take the user to the form

                var buttonText = "Enter " + form.getLocalized("name", self.options.language);
                var buttonUrl = getFormEntryUrl(self.options.urlRoot,
                                                        form.get("app_id"),
                                                        form.get("module_index"),
                                                        form.get("index"),
                                                        caseModel.id);
                var buttonOnClick = function () {
                    self.playForm(module, form, caseModel);
                }
            } else {
                // Construct a button which will take the user to the next list of cases
                // Note: The case_label should be plural for this button e.g. "View Mothers"
                //       But, in the currently selected case heading we want a singular version
                //       e.g. "Mother: Mary"
                var buttonText = "View " + self.selectedModule.get("case_label")[self.options.language];
                var buttonUrl = getChildSelectUrl(self.options.urlRoot,
                                                        form.get("app_id"),
                                                        form.get("module_index"),
                                                        form.get("index"),
                                                        caseModel.id);
                var buttonOnClick = function () {
                    cloudCare.dispatch.trigger("parent:selected", caseModel);
                }
            }
            //formListView.enterForm is now a misnomer because sometimes this element is about viewing more cases.
            self.formListView.enterForm = $("<a />").text(
                buttonText
            ).addClass("btn btn-primary").appendTo(
                self.formListView.caseView.detailsView.el
            );
            $('<a />').attr('href', buttonUrl).attr('target', '_blank').text(translatedStrings.newWindow).appendTo(
                self.formListView.caseView.detailsView.el
            ).css("padding-left", "2em");
            self.formListView.enterForm.click(buttonOnClick);
        } else {
            if (self.formListView.enterForm) {
                self.formListView.enterForm.detach();
                self.formListView.enterForm = null;
            }
        }
    },
    showModule: function (module) {
        var self = this;
        self._clearMainPane();
        self.selectedModule = module;
        self.formListView.model = module;
        self.formListView.render();
    },
    getFormUrl: function (module, form, caseModel) {
        var self = this;
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
        if (typeof caseModel !== 'undefined') {
            url += "?case_id=" + caseModel.id;
            if (form.get('index') === 'task-list') {
                url += "&task-list=true";
            }
        }

        // superhacky
        if ($('#use-offline').is(':checked')) {
            url += (url.indexOf('?') != -1 ? '&' : '?');
            url += "offline=true"
        }

        return url;
    },
    playSession: function (session) {
        var self = this;
        var session_id = session.get('id');

        var resp = $.ajax({
            url: getSessionContextUrl(self.options.sessionUrlRoot, session_id),
            async: false,
            dataType: "json"
        });
        resp.done(function (data) {
            return self._playForm(data);
        });

    },
    playForm: function (module, form, caseModel) {
        // go play the form. this is a little sketchy
        var self = this;
        cloudCare.dispatch.trigger("form:enter", form, caseModel);
        var formUrl = self.getFormUrl(module, form, caseModel);

        // get context
        var resp = $.ajax({
            url: formUrl,
            async: false,
            dataType: "json"
        });
        resp.done(function (data) {
            self._playForm(data, {form: form, caseModel: caseModel});
        });
    },
    _playForm: function (data, options) {

        var self = this;
        options = options || {};

        // clear current case tables
        self._clearMainPane();
        var form = options.form;
        var caseModel = options.caseModel;
        var submitUrl = self.model.getSubmitUrl();
        var selectedModule = self.formListView.model;
        self.caseSelectionView.model.set("parentCase", self.selectedParent);
        if (caseModel) {
            caseModel.set("module", selectedModule);
            self.caseSelectionView.model.set("childCase", caseModel);
        }

        data.formContext = {
            case_model: caseModel ? caseModel.toJSON() : null
        };
        data.onsubmit = function (xml) {
            window.mainView.router.view.dirty = false;
            // post to receiver
            $.ajax({
                type: 'POST',
                url: submitUrl,
                data: xml,
                success: function () {
                    self._clearFormPlayer();
                    self.showModule(selectedModule);
                    cloudCare.dispatch.trigger("form:submitted");
                    showSuccess(translatedStrings.saved, $("#cloudcare-notifications"), 2500);
                },
                error: function (resp, status, message) {
                    if (message) {
                        message = translatedStrings.errSavingDetail + message;
                    } else {
                        message = translatedStrings.unknownError + status + " " + resp.status;
                        if (resp.status === 0) {
                            message = (message + ". "
                                + translatedStrings.unknownErrorDetail + " (" + submitUrl + ")");
                        }
                    }
                    data.onerror({message: message});
                    // TODO change submit button text to something other than
                    // "Submitting..." and prevent "All changes saved!" message
                    // banner at top of the form.
                }
            });
        };
        data.onerror = function (resp) {
            showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
            cloudCare.dispatch.trigger("form:error", form, caseModel);
        };
        data.onload = function (adapter, resp) {
            cloudCare.dispatch.trigger("form:ready", form, caseModel);
        };
        data.answerCallback = function(sessionId) {
            if (self.options.instanceViewerEnabled && $('#auto-sync-control').is(':checked')) {
                $.ajax({
                    url: self.options.renderFormRoot,
                    data: {'session_id': sessionId},
                    success: function (data) {
                        showRenderedForm(data.instance_xml, $("#xml-viewer-pretty"));
                        showRenderedForm(data.form_data, $("#question-viewer-pretty"));
                    }
                });
            }
        };
        data.resourceMap = function(resource_path) {
            if (resource_path.substring(0, 7) === 'http://') {
                return resource_path;
            } else if (self.model.attributes.hasOwnProperty("multimedia_map") &&
                self.model.attributes.multimedia_map.hasOwnProperty(resource_path)) {
                var resource = self.model.attributes.multimedia_map[resource_path];
                var id = resource.multimedia_id;
                var media_type = resource.media_type;
                var name = _.last(resource_path.split('/'));
                return '/hq/multimedia/file/' + media_type + '/' + id + '/' + name;
            }
        };
        var loadSession = function() {
            var sess = new WebFormSession(data);
            // TODO: probably shouldn't hard code these divs
            sess.load($('#webforms'), self.options.language, {
                onLoading: tfLoading,
                onLoadingComplete: tfLoadingComplete
            });
        };
        var promptForOffline = function(show) {
            $('#offline-prompt')[show ? 'show' : 'hide']();
        };
        touchformsInit(data.xform_url, loadSession, promptForOffline);
    },
    selectForm: function (form) {
        var self = this;
        var formListView = self.formListView;
        self.selectedForm = form;
        self._clearFormPlayer();

        if (form) {
            var module = self.moduleListView.getModuleView(form.get('module_index')).model;
            var module_index = form.get("module_index");
            // clear anything existing
            self._clearCaseView();

            if (form.get("requires") === "none") {
	            // no requirements, go ahead and play it
	            self.playForm(module, form);

            } else if (form.get("requires") === "case") {
                // If a parent is selected, we want to filter the cases differently.
                if (self.selectedParent){
                    cloudCare.dispatch.trigger("form:selected:parent:caselist", form, self.selectedParent.id);
                    self.caseSelectionView.model.set("parentCase", self.selectedParent);
                } else {
                    cloudCare.dispatch.trigger("form:selected:caselist", form);
                }

                var parentSelectActive = module.get("parent_select").active;
                if (parentSelectActive && !self.selectedParent) {
                    var parent_module_id = module.get("parent_select").module_id;
                    var parent_module_index = 0;
                    var parent_module = null;

                    while (parent_module === null) {
                        var possible_parent = self.moduleListView.getModuleView(parent_module_index).model;
                        if (possible_parent.get("unique_id") === parent_module_id) {
                            parent_module = possible_parent;
                        } else {
                            parent_module_index += 1;
                        }
                    }

                    module = parent_module;
                    module_index = parent_module_index;
                }
                parentId = self.selectedParent ? self.selectedParent.id : null
	            var listDetails = module.get("case_details").short;
	            var summaryDetails = module.get("case_details").long;
	            formListView.caseView = new cloudCare.CaseMainView({
	                el: $("#cases"),
	                listDetails: listDetails,
	                summaryDetails: summaryDetails,
	                appConfig: {
                        app_id: form.get("app_id"),
	                    module_index: form.get("module_index"),
                        form_index: form.get("index"),
                        module: module,
                        parentSelectActive: parentSelectActive,
                        parentId: parentId
                    },
	                language: formListView.options.language,
	                caseUrl: getCaseFilterUrl(
                        self.options.caseUrlRoot,
                        form.get("app_id"),
                        module_index,
                        // index is passed in so that if it's equal to 'task-list' that'll be taken into account
                        // otherwise it's ignored
                        form.get('index'),
                        parentId
                    ),
                    parent: self.selectedParent
	            });

	            formListView.caseView.listView.caseList.on("reset", function () {
	                cloudCare.dispatch.trigger("cases:updated");
	            });
	        }
        }
    },
    selectParent: function(parent){
        this.selectedParent = parent;
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
        var self = this,
            caseView = self.formListView.caseView;
        if (caseView) {
            $(caseView.el).html("");
        }
    },
    _clearFormPlayer: function () {
        // TODO: clean hack/hard coded id
        //       One posibility would be to set an `el` for this View. Then the id is only in one place.
        $('#webforms').html("");
        this.caseSelectionView.model.set("parentCase", null);
        this.caseSelectionView.model.set("childCase", null);
    }
});

cloudCare.AppMainView = Backbone.View.extend({
    el: $('#app-main'),

    TITLE_SUFFIX: ' - CommCareHQ',
    TITLE_DEFAULT: 'Cloudcare',

    initialize: function () {
        var self = this;
        _.bindAll(self, "render", 'selectApp', "clearCases", "clearForms",
                  "clearModules", "clearAll", "navigate", "updateTitle");

        self._appCache = {};
        self._selectedModule = null;
        self._selectedForm = null;
        self._selectedParent = null;
        self._selectedCase = null;
        self._navEnabled = true;
        self.router = new cloudCare.AppNavigation();
        self._sessionsEnabled = self.options.sessionsEnabled;

        // set initial data, if any
        if (self.options.initialApp) {
            self.initialApp = new cloudCare.App(self.options.initialApp);
            self._appCache[self.initialApp.id] = self.initialApp;
        }
        if (self.options.initialCase) {
            self.initialCase = new cloudCare.Case(self.options.initialCase);
        }
        if (self.options.initialParent) {
            self.initialParent = new cloudCare.Case(self.options.initialParent);
        }

        self.appListView = new cloudCare.AppListView({
            apps: self.options.apps,
            language: self.options.language
        });

        self.appView = new cloudCare.AppView({
            // if you pass in model: it will auto-populate the view
            model: self.initialApp,
            language: self.options.language,
            caseUrlRoot: self.options.caseUrlRoot,
            urlRoot: self.options.urlRoot,
            sessionUrlRoot: self.options.sessionUrlRoot,
            submitUrlRoot: self.options.submitUrlRoot,
            renderFormRoot: self.options.renderFormRoot,
            instanceViewerEnabled: self.options.instanceViewerEnabled
        });

        // fetch session list here
        if (self._sessionsEnabled) {
            self.sessionListView = new cloudCare.SessionListView({
                sessionUrl: self.options.sessionUrlRoot
            });
            cloudCare.dispatch.on(
                'app:selected app:deselected module:selected module:deselected form:selected form:deselected form:submitted',
                function (e, f) {
                    self.sessionListView.reset();
                }
            );


        }

        cloudCare.dispatch.on("app:selected", function (app) {
            self.navigate("view/" + app.model.id);
            self.selectApp(app.model.id);
            self.updateTitle(app.model.get('name'));
        });
        cloudCare.dispatch.on("app:deselected", function (app) {
            self._selectedModule = null;
            self.navigate("");
            self.selectApp(null);
            self.updateTitle(null);
        });

        // utilities
        var selectApp = function (appId) {
            var appView = self.appListView.getAppView(appId);
            if (appView) {
                appView.select();
            }
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

        var selectForm = function (formIndex, options) {
            var formView = self.appView.formListView.getFormView(formIndex);
            if (formView) {
                formView.select(options);
            }
            self._selectedForm = formIndex;
        };

        var selectParent = function (parentId){
            var caseMainView = self.appView.formListView.caseView;
            if (caseMainView) {
                var caseView = caseMainView.listView.caseMap[parentId];
                if (caseView) {
                    /*
                        If selectParent is called immediately after selectForm
                        (like in clearAndSelectFormWithParent), then this block
                        almost certainly will not be entered. When selectForm
                        is called, the caseMainView.listView is populated by
                        making an ajax call to the server. Thus, the caseMap
                        will be empty until that request finishes.

                        Therefore, setting self._selectedParent is very
                        important. When the caseMainView is finished updating
                        it will trigger a "cases:updated" event. The
                        "cases:updated" handler defined below will check if
                        self._selectedParent is set. If it is, the
                        "parent:selected" event will be triggered. and
                        self._selectedParent will be cleared.

                        An analogous process happens if selectCase is called
                        immediately following selectForm
                     */
                    cloudCare.dispatch.trigger("parent:selected", caseView.model);
                }
            }
            self._selectedParent = parentId;
        };

        var selectCase = function (caseId) {
            var caseMainView = self.appView.formListView.caseView;
            if (caseMainView) {
                var caseView = caseMainView.listView.caseMap[caseId];
                if (caseView) {
                    // see the note in selectParent for an explanation
                    // of the control flow that happens when selectCase
                    // is called.
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
        self.router.on("route:clear", pauseNav(function () {
            self.clearAll();
        }));

        var _stripParams = function (val) {
            if (val.indexOf("?") !== -1) {
                return val.substring(0, val.indexOf("?"));
            }
            return val;
        };
        self.router.on("route:app", pauseNav(function (appId) {
            self.clearModules();
            selectApp(_stripParams(appId));
        }));

        self.router.on("route:app:module", pauseNav(function (appId, moduleIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(_stripParams(moduleIndex));
        }));

        var clearAndSelectForm = function (appId, moduleIndex, formIndex) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(_stripParams(formIndex));
        };

        var clearAndSelectFormWithParent = function (appId, moduleIndex, formIndex, parentId) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex);
            selectParent(_stripParams(parentId));
        };

        self.router.on("route:app:module:form", pauseNav(clearAndSelectForm));
        self.router.on("route:app:module:form:parent", pauseNav(clearAndSelectFormWithParent));
        self.router.on("route:app:module:form:enter", pauseNav(clearAndSelectForm));

        var clearAndSelectCase = function (appId, moduleIndex, formIndex, caseId) {
            self.clearForms();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex);
            selectCase(_stripParams(caseId));
        };

        var clearAndSelectCaseWithParent = function (appId, moduleIndex, formIndex, parentId, caseId) {
            clearAndSelectFormWithParent(appId, moduleIndex, formIndex, parentId);
            selectCase(_stripParams(caseId));
        };

        self.router.on("route:app:module:form:case", pauseNav(clearAndSelectCase));
        self.router.on("route:app:module:form:parent:case", pauseNav(clearAndSelectCaseWithParent));
        self.router.on("route:app:module:form:case:enter", pauseNav(function (appId, moduleIndex, formIndex, caseId) {
            self.clearCases();
            selectApp(appId);
            selectModule(moduleIndex);
            selectForm(formIndex, {noEvents: true});

            if (self.initialApp && self.initialApp.id === appId &&
                self.initialCase && self.initialCase.id === caseId) {
                var app = new cloudCare.App(self.initialApp);
                var module = app.modules[moduleIndex];
                var form = module.forms[formIndex];
                // Why make a new instance of this object?
                var caseModel = new cloudCare.Case(self.initialCase);

                if (module.get("parent_select").active) {
                    if (self.initialParent){

                        var parentModuleId = module.get("parent_select").module_id;
                        var parentModule = null;
                        var parentModuleIndex = null;
                        var modules = self.appView.moduleListView.moduleList.models;
                        for(var i = 0; i < modules.length; i++){
                            if (modules[i].get("unique_id") === parentModuleId){
                                parentModule = modules[i];
                                parentModuleIndex = i;
                                break;
                            }
                        }
                        self.initialParent.set('appConfig', {
                            app_id: appId,
                            module_index: moduleIndex,
                            form_index: formIndex,
                            module: parentModule,
                            parentSelectActive: true,
                            parentId: self.initialParent.id
                        });
                        self.appView.selectParent(self.initialParent);

                    } else {
                        // We could only get here if a user enters an incorrect url
                        throw 'Bad initial state';
                    }
                }
                self.appView.playForm(module, form, caseModel);
            } else {
                // we never expect to get here
                throw 'Bad initial state';
            }
        }));

        // these are also incoming routes, that look funny because of how the event
        // spaghetti resolves.
        self.appView.moduleListView.on("modules:updated", function () {
            // this selects an appropriate module any time they are updated.
            // we have to be careful to clear this field anytime a module
            // is deselected
            if (self._selectedModule !== null) {
                this.getModuleView(self._selectedModule).select();
            }
            self._selectedModule = null;
        });
        cloudCare.dispatch.on("cases:updated", pauseNav(function () {
            // same trick but with cases

            // See the note in selectCase for an explanation of how this
            // event handler fits in to the control flow of this page.
            if (self._selectedCase !== null) {
                // If self._selectedCase is not in the caseMap, that means this is the first time cases:updated has been triggered, and therefore the case list is showing the possible parent cases.
                // If self._selectedCase is in the caseMap, that means that this is the second time cases:updated has been triggered, and therefore the case list is showing the child cases of the parent case.
                var caseView = self.appView.formListView.caseView.listView.caseMap[self._selectedCase];
                if (caseView){
                    self.appView.formListView.caseView.listView.caseMap[self._selectedCase].select();
                    // We only want to clear self._selectedCase if the caseView was actually selected.
                    self._selectedCase = null;
                }
            }

            if (self._selectedParent !== null) {
                var parentModel = self.appView.formListView.caseView.listView.caseMap[self._selectedParent].model;
                cloudCare.dispatch.trigger("parent:selected", parentModel);
            }
            self._selectedParent = null;
        }));

        // setting routes
        cloudCare.dispatch.on("module:selected", function (module) {
            self.navigate("view/" + module.get("app_id") +
                                 "/" + module.get("index"));
            // hack to resolve annoying event-driven dependencies (see below)
            self.trigger("module:selected");
            self.updateTitle(module.get('name')[self.options.language]);
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

            self.updateTitle(self.app.get('name'));
        });

        cloudCare.dispatch.on('form:selected', function(form) {
            self.updateTitle(form.get('name')[self.options.language]);
        });
        cloudCare.dispatch.on("form:selected:caselist", function (form) {
            self.navigate("view/" + form.get("app_id") +
                "/" + form.get("module_index") +
                "/" + form.get("index"));
        });
        cloudCare.dispatch.on("form:selected:parent:caselist", function (form, parentId) {
            self.navigate("view/" + form.get("app_id") +
                                 "/" + form.get("module_index") +
                                 "/" + form.get("index") +
                                 "/parent/" + parentId);
        });
        cloudCare.dispatch.on("form:deselected", function (form) {
            self.navigate("view/" + form.get("app_id") +
                                 "/" + form.get("module_index"));
            self.clearForms();

            // After deselect form, update with selected module if it exists
            var module = self.app.modules[self._selectedModule];
            self.updateTitle(module ? module.get('name')[self.options.language] : null);
        });
        cloudCare.dispatch.on("form:enter", function (form, caseModel) {
            var caseId;
            if (typeof caseModel !== 'undefined') {
                caseId = caseModel.id;
            }
            var path = getFormEntryPath(form.get("app_id"),
                                        form.get("module_index"),
                                        form.get("index"),
                                        caseId);
            self.navigate(path, {replace: true});
            self.updateTitle(form.get('name')[self.options.language]);
        });
        cloudCare.dispatch.on("case:selected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            var parentSection = appConfig.parentId ? "/parent/" + appConfig.parentId : "";
            self.navigate("view/" + appConfig.app_id +
                                 "/" + appConfig.module_index +
                                 "/" + appConfig.form_index +
                                 parentSection +
                                 "/case/" + caseModel.id);
            // The following has to happen after navigate's done,
            // but navigate is non-blocking, so we have to stick it at the end of the queue
            // (gross)
            setTimeout(function () {
                self.appView.selectCase(caseModel);
            }, 0);
        });
        cloudCare.dispatch.on("case:deselected", function (caseModel) {
            var appConfig = caseModel.get("appConfig");
            var parentSection = appConfig.parentId ? "/parent/" + appConfig.parentId : "";
            self.navigate("view/" + appConfig.app_id +
                                 "/" + appConfig.module_index +
                                 "/" + appConfig.form_index +
                                 parentSection);
            self.appView.selectCase(null);
        });
        cloudCare.dispatch.on("session:selected", function (session) {
            self.playSession(session);
        });
    },

    updateTitle: function(title) {
        $('title').text((title || this.TITLE_DEFAULT) + this.TITLE_SUFFIX);
    },

    navigate: function (path, options) {
        if (this._navEnabled) {
            this.router.navigate(path, options);
        }
    },
    selectApp: function (appId, options) {
        var self = this;
        options = options || {};
        if (appId === null) {
            self.clearAll();
        } else {
            var app = self._appCache[appId];
            if (!app) {
                app = new cloudCare.App({
	                _id: appId
                });
                app.set("urlRoot", self.options.appUrlRoot);
                showLoading();
                var callback = function (model) {
                    self.appView.setModel(model);
                    self.appView.render();
                    hideLoading();
                    self._appCache[appId] = app;
                }
                if (options.async === false) {
                    app.fetch({async: false});
                    callback(app);
                }
                else {
                    app.fetch({success: callback});
                }
            } else {
                self.appView.setModel(app);
                self.appView.render();
            }
            self.app = app;
	    }
    },
    playSession: function (session) {
        var self = this;
        self.clearForms();
        self.selectApp(session.get('app_id'), {async: false});
        self.appView.playSession(session);
    },
    clearCases: function () {
        this._selectedCase = null;
    },
    clearForms: function () {
        this.clearCases();
        this._selectedParent = null;
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
