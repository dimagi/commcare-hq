import $ from 'jquery';
import 'select2/dist/js/select2.full.min';
import Alpine from 'alpinejs';

import utils from 'hqwebapp/js/alpinejs/directives/select2';

const _createMultiOptionSelect2 = (el, propId, propertyDetails) => {
    const propertyInfo = (propId) ? propertyDetails[propId] : {};
    if (propertyInfo.data_type === 'multiple_option') {
        utils.select2Cleanup(el);
        $(el).empty();
        $(el).select2({
            tags: true,
            tokenSeparators: [',', ' '],
            multiple: true,
            data: propertyInfo.options.map((x) => {
                return {id: x, text: x};
            }),
            language: {
                noResults: () => {
                    return gettext("No available suggestions. Add more by separating words with spaces.");
                },
            },
        });
    }
};

Alpine.directive('dynamic-options-select2', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-dynamic-options-select2 to your select element.
     * Creates the select2 field with suggested options for "Multiple Option/Choice"
     * case property data types. Use only for the Bulk Data Cleaning UI.
     *
     *      <select x-dynamic-options-select2="{% html_attr config %}"></select>
     *
     *      Where `config` is an object with the following options:
     *      {
     *          eventName: <string - name of the event to listen for changes to `propId`>,
     *          details: <object - the output of `get_case_property_details`>,
     *          initialPropId: <string - initial prop_id (if selected)>,
     *      }
     *
     */
    const config = (expression) ? JSON.parse(expression) : {};
    if (config.initialPropId) {
        _createMultiOptionSelect2(el, config.initialPropId, config.details);
    }
    window.addEventListener(config.eventName, (event) => {
        const propId = event.detail.value;
        _createMultiOptionSelect2(el, propId, config.details);
    });
    cleanup(() => {
        utils.select2Cleanup(el);
    });
});

document.body.addEventListener('htmx:afterSettle', (event) => {
    utils.fixSelect2htmx(event, '[x-dynamic-options-select2]');
});
