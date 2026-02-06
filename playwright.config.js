/* globals module, process, require */
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './playwright',
    timeout: 120000,
    expect: {
        timeout: 10000,
    },
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: [['list'], ['html', { open: 'never' }]],
    use: {
        baseURL: process.env.BASE_URL || 'http://localhost:8000',
        trace: 'on-first-retry',
        headless: true,
    },
    projects: [
        {
            name: 'chromium',
            use: { browserName: 'chromium' },
        },
    ],
    webServer: undefined, // Django server must be started separately
});
