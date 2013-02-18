/*
 Legacy, should deal with replacing these soon?
 */
var COMMCAREHQ = (function () {
    'use strict';
    return {
        initBlock: function ($elem) {
            $('.post-link').click(function (e) {
                e.preventDefault();
                $.postGo($(this).attr('href'), {});
            });
        },
        makeHqHelp: function (opts, wrap) {
            wrap = wrap === undefined ? true : wrap;
            var el = $(
                '<a href="#" class="hq-help no-click">' +
                    '<i class="icon-question-sign" data-trigger="hover"></i></a>'
            );
            for (var attr in {'content': 0, 'title': 0}) {
                $('i', el).data(attr, opts[attr]);
            }
            if (wrap) {
                el.hqHelp();
            }
            return el;
        },
        updateDOM: function (update) {
            var key;
            for (key in update) {
                if (update.hasOwnProperty(key)) {
                    $(key).text(update[key]);
                }
            }
        },
        SaveButton: SaveButton
    };
}());

var eventize = function (that) {
    'use strict';
    var events = {};
    that.on = function (tag, callback) {
        if (events[tag] === undefined) {
            events[tag] = [];
        }
        events[tag].push(callback);
        return that;
    };
    that.fire = function (tag, e) {
        var i;
        if (events[tag] !== undefined) {
            for (i = 0; i < events[tag].length; i += 1) {
                events[tag][i].apply(that, [e]);
            }
        }
        return that;
    };
    return that;
};

var SaveButton = {
    /*
     options: {
     save: "Function to call when the user clicks Save",
     unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
     }
     */
    init: function (options) {
        var button = {
            $save: $('<span/>').text(SaveButton.message.SAVE).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $saving: $('<span/>').text(SaveButton.message.SAVING).addClass('btn disabled'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn disabled'),
            ui: $('<div/>').css({float: 'right'}),
            setStateWhenReady: function (state) {
                if (this.state === 'saving') {
                    this.nextState = state;
                } else {
                    this.setState(state);
                }
            },
            setState: function (state) {
                if (this.state === state) {
                    return;
                }
                this.state = state;
                this.$save.detach();
                this.$saving.detach();
                this.$saved.detach();
                this.$retry.detach();
                if (state === 'save') {
                    this.ui.append(this.$save);
                } else if (state === 'saving') {
                    this.ui.append(this.$saving);
                } else if (state === 'saved') {
                    this.ui.append(this.$saved);
                } else if (state === 'retry') {
                    this.ui.append(this.$retry);
                }
            },
            ajax: function (options) {
                var beforeSend = options.beforeSend || function () {},
                    success = options.success || function () {},
                    error = options.error || function () {},
                    that = this;
                options.beforeSend = function () {
                    that.setState('saving');
                    that.nextState = 'saved';
                    beforeSend.apply(this, arguments);
                };
                options.success = function (data) {
                    that.setState(that.nextState);
                    success.apply(this, arguments);
                };
                options.error = function (data) {
                    that.nextState = null;
                    that.setState('retry');
                    alert(SaveButton.message.ERROR_SAVING);
                    error.apply(this, arguments);
                };
                $.ajax(options);
            }
        };
        eventize(button);
        button.setState('saved');
        button.on('change', function () {
            this.setStateWhenReady('save');
        });
        if (options.save) {
            button.on('save', options.save);
        }
        $(window).bind('beforeunload', function () {
            var stillAttached = button.ui.parents()[button.ui.parents().length - 1].tagName.toLowerCase() == 'html';
            if (button.state !== 'saved' && stillAttached) {
                return options.unsavedMessage || "";
            }
        });
        return button;
    },
    initForm: function ($form, options) {
        var url = $form.attr('action'),
            button = SaveButton.init({
                unsavedMessage: options.unsavedMessage,
                save: function () {
                    this.ajax({
                        url: url,
                        type: 'POST',
                        dataType: 'json',
                        data: $form.serialize(),
                        success: options.success
                    });
                }
            }),
            fireChange = function () {
                button.fire('change');
            };
        $form.find('*').change(fireChange);
        $form.find('input, textarea').bind('textchange', fireChange);
        return button;
    },
    message: {
        SAVE: 'Save',
        SAVING: 'Saving...',
        SAVED: 'Saved',
        RETRY: 'Try Again',
        ERROR_SAVING: 'There was an error saving'
    }
};

// thanks to http://stackoverflow.com/questions/1149454/non-ajax-get-post-using-jquery-plugin
// thanks to http://stackoverflow.com/questions/1131630/javascript-jquery-param-inverse-function#1131658

(function () {
    'use strict';
    $.extend({
        getGo: function (url, params) {
            document.location = url + '?' + $.param(params);
        },
        postGo: function (url, params) {
            var $form = $("<form>")
                .attr("method", "post")
                .attr("action", url);
            $.each(params, function (name, value) {
                $("<input type='hidden'>")
                    .attr("name", name)
                    .attr("value", value)
                    .appendTo($form);
            });
            $form.appendTo("body");
            $form.submit();
        },
        unparam: function (value) {
            var
                // Object that holds names => values.
                params = {},
                // Get query string pieces (separated by &)
                pieces = value.split('&'),
                // Temporary variables used in loop.
                pair, i, l;

            // Loop through query string pieces and assign params.
            for (i = 0, l = pieces.length; i < l; i += 1) {
                pair = pieces[i].split('=', 2);
                // Repeated parameters with the same name are overwritten. Parameters
                // with no value get set to boolean true.
                params[decodeURIComponent(pair[0])] = (pair.length === 2 ?
                    decodeURIComponent(pair[1].replace(/\+/g, ' ')) : true);
            }

            return params;
        }
    });

    $.fn.closest_form = function () {
        return this.closest('form, .form');
    };
    $.fn.my_serialize = function () {
        var data = this.find('[name]').serialize();
        return data;
    };

}());
