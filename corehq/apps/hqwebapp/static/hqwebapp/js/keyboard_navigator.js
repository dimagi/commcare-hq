/* requires keymaster.js to be included and key() to be aliased as KEY() in the global namespace */

var keyboard_navigator_utils = {
    focus_in_fn: function($ele) {
        $ele.addClass('hovered');
        $ele.trigger('mouseenter');
        $ele.focus();
    },
    focus_out_fn: function($ele) {
        if ($ele) {
            $ele.removeClass('hovered');
            $ele.trigger('mouseleave');
            $ele.blur();
        }
    }
};

var KeyboardNavigator = function() {
    KEY.setScope('ready');
    var last_mover = '';
    var KeyboardNavigator = function() {
        var self = this;
        self.elements_generated = false;
        self.navigating = false;
        self.prior_scope = false;


        self.init = function(options) {
            self.focus_in_fn = options.focus_in_fn || keyboard_navigator_utils.focus_in_fn;
            self.focus_out_fn = options.focus_out_fn || keyboard_navigator_utils.focus_out_fn;
            self.action_fn = options.action_fn || self.action_fn;
            self.start_fn = options.start_fn;
            self.stop_fn = options.stop_fn;
            self.leave_context = options.leave_context_fn || self.leave_context;
            self.gen_elements = options.element_list_generator;
            self.reset_index = options.reset_index !== false;

            self.name = options.name || '_unnamed_';
            self.ready_scope = options.ready_scope || 'ready';
            self.nav_key = options.nav_key || 'option';
            self.action_key = options.action_key || 'enter';
            self.forward_keys = options.forward_keys || ['right'];
            self.back_keys = options.back_keys || ['left'];

            self.regen_list_on_exit = options.regen_list_on_exit === true;

            self.macchrome_keycodes = {
                shift: 16,
                ctrl: 17,
                option: 18,
                command: 91
            };

            $(function() {
                $(document).keyup(function(event) {
                    if (KEY.getScope() === self.ready_scope) {
                        if ( event.which === self.macchrome_keycodes[self.nav_key] ) {
                            self.leave_nav();
                        }
                    }
                });

                KEY(self.nav_key, self.ready_scope, self.enter_nav);

                var set_up_nav_key_handlers = function(key) {
                    KEY(self.nav_key + '+' + key, self.ready_scope, self.gen_handle_nav(key));
                };
                _.each(self.forward_keys, set_up_nav_key_handlers);
                _.each(self.back_keys, set_up_nav_key_handlers);
                KEY(self.nav_key + '+' + self.action_key, self.ready_scope, self.handle_action);
                KEY(self.nav_key + '+' + 'space', self.ready_scope, self.handle_action);
            });
        };

        self.leave_context = function(side) {
            self.set_index(side === 'end' ? 0 : self.$elements.length - 1)
        };

        self.set_index = function(num) {
            if (num < 0) {
                self.leave_context('beginning');
            } else if (num >= self.$elements.length) {
                self.leave_context('end');
            } else {
                self.index = num;
                self.$active_element = $(self.$elements.get(self.index % self.$elements.length));
                last_mover = self.name;
            }
        };

        self.enter_nav = function() {
            if (self.regen_list_on_exit || !self.elements_generated) {
                self.$elements = self.gen_elements();
                self.elements_generated = true;
                self.set_index(0);
            }

            if (self.start_fn) {
                self.start_fn();
            }

            if (self.reset_index) {
                self.set_index(0);
            }

            console.log('Entering navigation: ' + self.name);
            console.log('Index set to: ' + self.index);
        };

        self.leave_nav = function() {
            console.log('Leaving navigation');

            self.handle_focus_out();
            KEY.setScope(self.ready_scope);
            self.navigating = false;

            if (self.stop_fn) {
                self.stop_fn();
            }

            if (self.prior_scope) {
                KEY.setScope(self.prior_scope);
                self.prior_scope = false;
            }
        };

        self.gen_handle_nav = function(key) {
            return function() {
                if (!self.navigating) {
                    self.enter_nav();
                }
                self.navigating = true;
                self.handle_focus_out();
                self.set_index(self.index + (self.forward_keys.indexOf(key) > -1 ? 1 : -1));
                self.handle_focus_in();
                return false;
            }
        };

        self.handle_focus_in = function() {
            console.log('hovering over...');
            console.log(self.$active_element.get(0));
            self.focus_in_fn(self.$active_element);
            return false;
        };

        self.handle_focus_out = function() {
            self.focus_out_fn(self.$active_element);
            return false;
        };

        self.action_fn = function($ele) {
            console.log(self);
            console.log($ele);
            $ele.click();
            // .click() only triggers a click event, below handles clicks for elements that have an href
            if ($ele.attr('href') && $ele.attr('href') != '#') {
                window.location = $ele.attr('href');
            }
        };

        self.handle_action = function() {
            // last_mover is a pseudo-global variable stored in a closure that keeps track of which kn moved last
            // only want to handle the action of this navigator if it was the last mover.
            console.log('action button pressed');
            if (last_mover === self.name) {
                self.action_fn(self.$active_element);
                self.leave_nav();
            }
            return false
        };

        self.activate = function() {
            self.prior_scope = KEY.getScope();
            KEY.setScope(self.ready_scope);
            self.enter_nav();
            self.handle_focus_in();
            return false;
        }
    };
    return KeyboardNavigator;
}();
