import 'commcarehq';
import 'hqwebapp/js/htmx_base';

import Alpine from 'alpinejs';
import 'hqwebapp/js/alpinejs/directives/datepicker';

document.addEventListener('alpine:init', () => {
    Alpine.data('formChoices', (initial) => ({
        apps: initial.apps,
        appId: '',
        menuId: '',
        formId: '',
        get menus() {
            const app = this.apps.find((app) => app.id === this.appId);
            return app ? app.menus : [];
        },
        get forms() {
            const menu = this.menus.find((menu) => menu.id === this.menuId);
            return menu ? menu.forms : [];
        },
    }));
});

Alpine.start();
