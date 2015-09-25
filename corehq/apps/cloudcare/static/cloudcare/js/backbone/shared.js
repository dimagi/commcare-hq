

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
        var dialog = true;
        if (this.disabled) {
            return;
        }
        if (window.mainView.router.view && window.mainView.router.view.dirty) {
            dialog = confirm(translatedStrings.sidebarDirty);
            if (dialog) {
                window.mainView.router.view.dirty = false;
            } else {
                return;
            }
        }
        if (this.selected) {
            this.deselect();
            this.trigger("deselected");
        } else {
            this.select();
        }
    },
    select: function (options) {
        if (!this.selected) {
            window.mainView.router.setView(this);
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

    disable: function () {
        this.disabled = true;
        this.$el.addClass("disabled");
    },

    enable: function () {
        this.disabled = false;
        this.$el.removeClass("disabled");
    }
});
