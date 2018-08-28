.PHONY: requirements upgrade-requirements

scripts/_vendor/pip-post-compile.sh:
	mkdir -p scripts/_vendor
	curl https://raw.githubusercontent.com/edx/edx-platform/e3b6cad173dee4ba969759102224ef12010938a7/scripts/post-pip-compile.sh \
	    > scripts/_vendor/pip-post-compile.sh

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements: scripts/_vendor/pip-post-compile.sh
	pip-compile -o requirements/requirements.txt requirements/requirements.in
	pip-compile -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile -o requirements/test-requirements.txt requirements/test-requirements.in
	pip-compile -o requirements/dev-requirements.txt requirements/dev-requirements.in
	pip-compile -o requirements/docs-requirements.txt requirements/docs-requirements.in
	bash scripts/pip-post-compile.sh requirements/*requirements.txt

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements: scripts/_vendor/pip-post-compile.sh
	pip-compile --upgrade -o requirements/requirements.txt requirements/requirements.in
	pip-compile --upgrade -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o requirements/test-requirements.txt requirements/test-requirements.in
	pip-compile --upgrade -o requirements/dev-requirements.txt requirements/dev-requirements.in
	pip-compile --upgrade -o requirements/docs-requirements.txt requirements/docs-requirements.in
	bash scripts/pip-post-compile.sh requirements/*requirements.txt
