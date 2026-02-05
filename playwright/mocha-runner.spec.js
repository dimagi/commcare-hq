// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

/**
 * Runs Mocha tests at a given URL and returns the results.
 * @param {import('@playwright/test').Page} page
 * @param {string} testPath - The path to the mocha test page (e.g., 'export')
 * @returns {Promise<{passes: number, failures: number, pending: number, duration: number, failureDetails: Array<{title: string, error: string}>}>}
 */
async function runMochaTests(page, testPath) {
    const url = `${BASE_URL}/mocha/${testPath}`;
    console.log(`Running tests at: ${url}`);

    await page.goto(url);

    // Wait for Mocha to finish running tests
    // Mocha adds #mocha-stats when tests complete
    await page.waitForSelector('#mocha-stats', { timeout: 60000 });

    // Small delay to ensure all results are rendered
    await page.waitForTimeout(500);

    // Extract test results from the DOM
    const results = await page.evaluate(() => {
        const passes = document.querySelectorAll('.test.pass').length;
        const failures = document.querySelectorAll('.test.fail').length;
        const pending = document.querySelectorAll('.test.pending').length;

        // Get duration from stats
        const durationEl = document.querySelector('#mocha-stats .duration em');
        const duration = durationEl ? parseFloat(durationEl.textContent || '0') : 0;

        // Collect failure details
        const failureDetails = [];
        document.querySelectorAll('.test.fail').forEach((el) => {
            const titleEl = el.querySelector('h2');
            const errorEl = el.querySelector('.error');

            // Get the full test title (includes parent describe blocks)
            let title = '';
            if (titleEl) {
                // Remove the duration span from the title
                const titleClone = titleEl.cloneNode(true);
                const durationSpan = titleClone.querySelector('.duration');
                if (durationSpan) {
                    durationSpan.remove();
                }
                title = titleClone.textContent?.trim() || 'Unknown test';
            }

            const error = errorEl ? errorEl.textContent?.trim() || 'No error message' : 'No error message';
            failureDetails.push({ title, error });
        });

        return { passes, failures, pending, duration, failureDetails };
    });

    return results;
}

/**
 * Prints test results in a readable format.
 */
function printResults(testName, results) {
    console.log('\n' + '='.repeat(60));
    console.log(`Test Suite: ${testName}`);
    console.log('='.repeat(60));
    console.log(`  Passed:  ${results.passes}`);
    console.log(`  Failed:  ${results.failures}`);
    console.log(`  Pending: ${results.pending}`);
    console.log(`  Duration: ${results.duration}s`);

    if (results.failureDetails.length > 0) {
        console.log('\nFailures:');
        results.failureDetails.forEach((failure, index) => {
            console.log(`\n  ${index + 1}) ${failure.title}`);
            console.log(`     Error: ${failure.error.substring(0, 200)}...`);
        });
    }
    console.log('='.repeat(60) + '\n');
}

// All test apps (same as Gruntfile.js)
const TEST_APPS = [
    'app_manager/bootstrap3',
    'app_manager/bootstrap5',
    'export',
    'notifications/bootstrap3',
    'notifications/bootstrap5',
    'reports_core/choiceListUtils',
    'locations',
    'userreports/bootstrap3',
    'userreports/bootstrap5',
    'cloudcare',
    'cloudcare/form_entry',
    'hqwebapp/bootstrap3',
    'hqwebapp/bootstrap5',
    'hqwebapp/components',
    'case_importer',
];

test.describe('Mocha Test Runner', () => {
    for (const app of TEST_APPS) {
        test(`${app}`, async ({ page }) => {
            const results = await runMochaTests(page, app);
            printResults(app, results);

            // Assert no failures
            expect(results.failures, `Expected 0 failures but got ${results.failures}`).toBe(0);
            expect(results.passes, 'Expected at least one passing test').toBeGreaterThan(0);
        });
    }
});
