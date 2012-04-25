
var getLocalizedString = function (property, language) {
    // simple utility to localize a string based on a dict of 
    // language mappings.
    return this.get(property)[language] || "?";
};

var getFormUrl = function(urlRoot, appId, moduleId, formId) {
    // TODO: make this cleaner
    return urlRoot + "view/" + appId + "/modules-" + moduleId + "/forms-" + formId + "/context/";
};

var getSubmitUrl = function (urlRoot, appId) {
    // TODO: make this cleaner
    return urlRoot + "/" + appId + "/";
};

var getCaseFilterUrl = function(urlRoot, appId, moduleId) {
    // TODO: make this cleaner
    return urlRoot + "module/" + appId + "/modules-" + moduleId + "/";
};

var showSuccess = function (message, location, autoHideTime) {
    var alert = $("<div />").addClass("alert alert-success").text(message);
    alert.append($("<a />").addClass("close").attr("data-dismiss", "alert").html("&times;"));
    location.append(alert);
    if (autoHideTime) {
        alert.delay(autoHideTime).fadeOut(500);
    }
};

var showLoading = function (selector) {
    selector = selector || "#loading";
    $(selector).show();
};

var hideLoading = function (selector) {
    selector = selector || "#loading";
    $(selector).hide();
};

var hideLoadingCallback = function () {
    hideLoading();
};

/*
 * A selectable UI element with default events and css classes.
 */
var Selectable = Backbone.View.extend({
    events: {
        "click": "toggle"
    },
    toggle: function () {
        if (this.selected) {
            this.deselect();
            this.trigger("deselected");
        } else {
            this.select();
        }
    }, 
    select: function () {
        if (!this.selected) {
	        this.selected = true;
	        this.$el.addClass("active");
	        this.trigger("selected");
        }
    }, 
    
    deselect: function () {
        this.selected = false;
        this.$el.removeClass("active");
    }, 
});
