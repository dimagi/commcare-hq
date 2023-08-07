# Run this with local development server active to report Javascript test coverage

# Save the local file state in a temporary branch
git checkout -b "temp-coverage-js"
git commit --allow-empty --no-verify -a -m "temp commit"

# Instrument HQ Javascript in place
npx nyc instrument -x "**/sentry" -x "**/spec" -x "**/mocha" -x "**/lib" \
    "corehq/apps" "corehq/apps" --in-place

# Run tests through grunt test task with coverage flag
grunt test --coverage

# Merge coverage data from multiple apps
npx nyc merge "./coverage-js" "./coverage-js/merged/coverage.json"

# Reset to previous git state before creating report
# This is done before the report is built to get accurate line-by-line coverage
git reset --hard

# Build the report based on merged coverage data
npx nyc report --temp-dir "./coverage-js/merged" --report-dir "./coverage-js" \
    --reporter "html" --reporter "text-summary"

# Unstage current changes, switch to prior working branch, delete temporary branch
git reset HEAD~1 && git switch - && git branch -D "temp-coverage-js"
