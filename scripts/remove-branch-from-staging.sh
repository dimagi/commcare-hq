#! /bin/bash

# sed -i '' "/ $1 /d" scripts/staging.yml
# git add scripts/staging.yml
# git commit -m "Removed $1 from staging.yml"
# git push origin master

# NOTE: start with testing to ensure expected diffs
sed "/ $1 /d" scripts/staging.yml > scripts/test-staging.yml
diff scripts/staging.yml scripts/test-staging.yml
