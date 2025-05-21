import { Tooltip } from 'bootstrap5';
import Alpine from 'alpinejs';


Alpine.directive('tooltip', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-tooltip to your element.
     *
     *      <div x-tooltip="{% html_attr config %}" >...</div>
     *
     *      Note: this tooltip will also understand `data-bs` attributes
     *      as defined in the Bootstrap docs.
     *
     */
    const config = expression ? JSON.parse(expression) : {};
    const tooltip = new Tooltip(el, config);
    cleanup(() => {
        tooltip.dispose();
    });
});
