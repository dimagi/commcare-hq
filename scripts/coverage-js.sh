# Generates local Javascript test coverage report

echo "Before running, please confirm:
   grunt is installed via npm or yarn
   local development server is active\n"
read -p "Do you want to proceed? (y/n) " proceed
case $proceed in
    y ) echo "Running Javascript coverage report"
        break;;
    * ) exit;;
esac

# Clean up the report directory if it already exists
if [ -d "./coverage-js" ]
then
    rm -r "./coverage-js"
fi

# Save the local file state in a temporary branch
git checkout -b "temp-coverage-js"
git commit --allow-empty --no-verify -a -m "temp commit"

# Instrument HQ Javascript in place
npx nyc instrument -x "**/lib" -x "**/sentry" -x "**/spec"  \
    -x "mocha" -x "hqmedia/static/hqmedia/MediaUploader" \
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
echo "\nView the full coverage report at:\033[96m\033[1m $(pwd)/coverage-js/index.html \033[0m\n"

# Unstage current changes, switch to prior working branch, delete temporary branch
git reset HEAD~1
if git branch --show-current | grep -q "temp-coverage-js"
then
    git switch - && git branch -D "temp-coverage-js"
fi
