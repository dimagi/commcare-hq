
var getLocalizedString = function (property, language) {
    // simple utility to localize a string based on a dict of 
    // language mappings.
    return this.get(property)[language] || "?";
};

var getFormUrl = function(urlRoot, appId, moduleId, formId) {
    // TODO: make this cleaner
    return urlRoot + "view/" + appId + "/modules-" + moduleId + "/forms-" + formId + "/";
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
