// Minimum options to boot the bundled Vellum
const VELLUM_OPTIONS = {
    core: {
        loadDelay: 0,
        formName: "Test Form",
        dataSourcesEndpoint: function (callback) { callback([]); },
        saveUrl: function () {},
    },
    javaRosa: {
        langs: ["en"],
        displayLanguage: "en",
    },
    features: {
        disable_popovers: true,
        rich_text: true,
    },
    intents: {
        templates: [{id: "intent", name: "Intent", mime: "text/plain"}],
    },
    plugins: [
        "databrowser",
        "saveToCase",
    ],
};

export default VELLUM_OPTIONS;
