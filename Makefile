.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=make requirements
requirements:
	pip-compile -o requirements/requirements.txt requirements/requirements.in
	pip-compile -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile -o requirements/build-requirements.txt requirements/build-requirements.in
	pip-compile -o requirements/dev-requirements.txt requirements/dev-requirements.in
	pip-compile -o requirements/docs-requirements.txt requirements/docs-requirements.in
	pip-compile -o requirements/test-requirements.txt requirements/test-requirements.in



upgrade-requirements: export CUSTOM_COMPILE_COMMAND=make upgrade-requirements
upgrade-requirements:
	pip-compile --upgrade -o requirements/requirements.txt requirements/requirements.in
	pip-compile --upgrade -o requirements/prod-requirements.txt requirements/prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o requirements/build-requirements.txt requirements/build-requirements.in
	pip-compile --upgrade -o requirements/dev-requirements.txt requirements/dev-requirements.in
	pip-compile --upgrade -o requirements/docs-requirements.txt requirements/docs-requirements.in
	pip-compile --upgrade -o requirements/test-requirements.txt requirements/test-requirements.in
