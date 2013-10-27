/* requires keymaster.js to be included and key() to be in the global namespace */

var KeyboardNavigator = function() {
    var self = this;
    self.ready_scope = 'ready';
    self.nav_scope = 'in navigation';

    self.init = function(options) {
        self.element_list = options.element_list;
        self.handle_hover = options.hover_fn || self.handle_hover ;
        self.handle_action = options.action_fn || self.handle_action ;

        self.nav_key = options.nav_key || 'option';
        self.action_key = options.action_key || 'enter';

        self.macchrome_keycodes = {
            shift: 16,
            ctrl: 17,
            option: 18,
            command: 91
        };

        $(function() {
            $(document).keyup(function(event) {
                if (key.getScope() === self.nav_scope) {
                    if ( event.which === self.macchrome_keycodes[self.nav_key] ) {
                        self.leave_nav();
                    }
                }
            });

            key.setScope(self.ready_scope);
            key(self.nav_key, self.ready_scope, self.enter_nav);
            key(self.nav_key + '+up', self.handle_nav('up'));
            key(self.nav_key + '+down', self.handle_nav('down'));
            key(self.nav_key + '+' + self.action_key, self.handle_action);

        });
    };

    self.enter_nav = function() {
        console.log('Entering navigation');
        key.setScope(self.nav_scope);
    };

    self.leave_nav = function() {
        console.log('Leaving navigation');
        key.setScope(self.ready_scope);
    };

    self.handle_nav = function(direction) {
        return function() {
            if (key.getScope() === self.ready_scope) {
                self.enter_nav();
            }
            console.log('Just went ' + direction);
        }
    };

    self.handle_hover = function() {
        console.log('hovering over')
    };

    self.handle_action = function() {
        console.log('action button pressed');
        self.leave_nav();
    };
};