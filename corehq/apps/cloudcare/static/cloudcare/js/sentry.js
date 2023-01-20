/* global Sentry */
hqDefine('cloudcare/js/sentry', [
    'hqwebapp/js/initial_page_data',
], function (
    initialPageData,
) {

    let initSentry = function () {
        const sentryConfig = initialPageData.get('sentry');

        if (sentryConfig.dsn) {
            Sentry.init({
                dsn: sentryConfig.dsn,
                environment: sentryConfig.environment,
                release: sentryConfig.release,
                initialScope: {
                    tags: { "domain": initialPageData.get('domain') },
                    user: { "username": initialPageData.get('username') },
                },
                integrations: [
                    new Sentry.Integrations.Breadcrumbs({
                        dom: false,
                        console: false,
                    }),
                ],
            });
        }
    };

    return {
        initSentry: initSentry
    };
});
