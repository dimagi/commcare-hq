import Sortable from 'sortablejs';
import Alpine from 'alpinejs';


Alpine.directive('htmx-sortable', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-htmx-sortable to your `<ul>` or similarly-styled `list-group`
     * parent.
     *
     * NOTE: This directive is intended to be paired with HTMX, which will do the sorting and
     * population of the list on the backend and re-render the partial.
     *
     * For an alpine-only client-side approach, see the `@alpinejs/sort` plugin,
     * or `x-sort`, which updates the alpine data model appropriately, sorting a list
     * defined in the model.
     *
     *      <div x-htmx-sortable="{% html_attr config %}">...</div>
     *
     */
    const config = expression ? JSON.parse(expression) : {};
    const indicatorClass = config.htmxIndicatorClass || 'htmx-indicator';
    const sortable = new Sortable(el, {
        animation: 150,
        // if present, make sure the HTMX indicator is not sortable
        filter: `.${indicatorClass}`,
        onMove: (evt) => {
            // make sure the htmx-indicator is never moved
            return evt.related.className.indexOf(indicatorClass) === -1;
        },
        onEnd: () => {
            sortable.option('disabled', true);
        },
    });
    cleanup(() => {
        sortable.destroy();
    });
});
