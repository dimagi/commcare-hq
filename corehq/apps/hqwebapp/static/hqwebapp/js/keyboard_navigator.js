/* requires keymaster.js to be included and key() to be in the global namespace */

var KeyboardNavigator = function() {
    var self = this;
    self.ready_scope = 'ready';
    self.nav_scope = 'in navigation';

    self.init = function(options) {
        self.handle_focus_in = options.handle_focus_in || self.handle_focus_in;
        self.handle_focus_out = options.handle_focus_out || self.handle_focus_out;
        self.handle_action = options.action_fn || self.handle_action;
        self.gen_elements = options.element_list_generator;
        self.reset_index = options.reset_index !== false;

        self.nav_key = options.nav_key || 'option';
        self.action_key = options.action_key || 'enter';
        self.forward_key = options.forward_key || 'right';
        self.back_key = options.back_key || 'left';

        self.macchrome_keycodes = {
            shift: 16,
            ctrl: 17,
            option: 18,
            command: 91
        };

        $(function() {
            self.$elements = self.gen_elements();
            self.set_index(0);

            $(document).keyup(function(event) {
                if (key.getScope() === self.nav_scope) {
                    if ( event.which === self.macchrome_keycodes[self.nav_key] ) {
                        self.leave_nav();
                    }
                }
            });

            key.setScope(self.ready_scope);
            key(self.nav_key, self.ready_scope, self.enter_nav);
            key(self.nav_key + '+' + self.forward_key, self.handle_nav(self.forward_key));
            key(self.nav_key + '+' + self.back_key, self.handle_nav(self.back_key));
            key(self.nav_key + '+' + self.action_key, self.handle_action);
        });
    };

    self.enter_nav = function() {
        if (self.reset_index) {
            self.set_index(0);
        }
        console.log('Entering navigation');
        console.log('Index set to: ' + self.index);
        key.setScope(self.nav_scope);
    };

    self.leave_nav = function() {
        console.log('Leaving navigation');
        self.handle_focus_out();
        key.setScope(self.ready_scope);
    };

    self.handle_nav = function(direction) {
        return function() {
            if (key.getScope() === self.ready_scope) {
                self.enter_nav();
            }
            self.handle_focus_out();
            self.set_index(self.index + (direction === self.forward_key ? 1 : -1));
            console.log('Just went ' + direction);
            console.log('index: ' + self.index);
            self.handle_focus_in();
            return false;
        }
    };

    self.handle_focus_in = function() {
        console.log('hovering over...');
        console.log(self.$active_element);
        self.$active_element.addClass('hovered');
        self.$active_element.trigger('mouseenter');
    };

    self.handle_focus_out = function() {
        self.$active_element.removeClass('hovered');
        self.$active_element.trigger('mouseleave');
    };

    self.handle_action = function() {
        $mock_ele = $('');
        console.log('action button pressed');
        self.$active_element.click();
        self.leave_nav();
    };

    self.set_index = function(num) {
        self.index = num;
        self.$active_element = $(self.$elements.get(self.index));
    }
};