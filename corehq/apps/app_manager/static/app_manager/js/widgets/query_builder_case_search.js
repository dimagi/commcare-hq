/**
 * Bridges case search data into the generic query builder component.
 *
 * - Defines the type/operator schema for case search variables.
 * - Registers a KO binding handler `syncQueryBuilderVariables` that watches
 *   search_properties and dispatches config updates.
 * - On Alpine init, loads static case properties from initialPageData.
 *
 * Import this module for its side effects (KO binding registration).
 * Call `initCasePropertyVariables()` after `Alpine.start()` to push
 * the static case properties into the query builder.
 */
import ko from 'knockout';
import initialPageData from 'hqwebapp/js/initial_page_data';

const types = [
    {
        name: 'search_field',
        operators: [
            {name: 'search matches', has_value: false},
            {name: 'equals', has_value: true},
            {name: 'not equals', has_value: true},
        ],
    },
    {
        name: 'text',
        operators: [
            {name: 'equals', has_value: true},
            {name: 'not equals', has_value: true},
            {name: 'is empty', has_value: false},
            {name: 'matches parameter', has_value: true},
        ],
    },
    {
        name: 'number',
        operators: [
            {name: 'equals', has_value: true},
            {name: 'greater than', has_value: true},
            {name: 'less than', has_value: true},
            {name: 'is empty', has_value: false},
        ],
    },
    {
        name: 'date',
        operators: [
            {name: 'equals', has_value: true},
            {name: 'before', has_value: true},
            {name: 'after', has_value: true},
            {name: 'is empty', has_value: false},
        ],
    },
];

let searchVariables = [];
let casePropertyVariables = [];

function dispatchConfig() {
    const variables = [...searchVariables, ...casePropertyVariables];
    window.dispatchEvent(new CustomEvent('query-builder:config', {
        detail: {types, variables},
    }));
}

function updateSearchVariables(searchProperties) {
    searchVariables = searchProperties
        .filter(p => p.name() && !p.isGroup)
        .map(p => ({
            id: p.name(),
            name: p.label() || p.name(),
            type: 'search_field',
        }));
    dispatchConfig();
}

ko.bindingHandlers.syncQueryBuilderVariables = {
    init: function (element, valueAccessor) {
        const searchProperties = valueAccessor();
        searchProperties.subscribe(function (props) {
            updateSearchVariables(props);
        });
        ko.computed(function () {
            searchProperties().forEach(function (p) {
                p.name();
                p.label();
            });
            updateSearchVariables(searchProperties());
        });
    },
};

/**
 * Load static case properties from page data and dispatch to the
 * query builder. Call this after Alpine.start().
 */
export function initCasePropertyVariables() {
    const details = initialPageData.get('details') || [];
    const caseDetail = details.find(d => d.type === 'case');
    if (caseDetail && caseDetail.properties) {
        casePropertyVariables = caseDetail.properties.map(name => ({
            id: name, name: name, type: 'text',
        }));
    }
    dispatchConfig();
}
