

/*
 * A localizable model, with a method "getLocalized"
 */

var LocalizableModel = Backbone.Model.extend({
    initialize: function () {
        _.bindAll(this, 'getLocalized');
    },
    getLocalized: getLocalizedString
});

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
    select: function (options) {
        if (!this.selected) {
	        this.selected = true;
	        this.$el.addClass("active");
	        if (typeof options === 'undefined' || !options.noEvents) {
	            this.trigger("selected");
	        }
        }
    }, 
    
    deselect: function () {
        this.selected = false;
        this.$el.removeClass("active");
    }, 
});
