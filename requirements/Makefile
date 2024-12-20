.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -qo requirements.txt requirements.in --allow-unsafe --strip-extras
	pip-compile -qo prod-requirements.txt prod-requirements.in --allow-unsafe --strip-extras
	pip-compile -qo test-requirements.txt test-requirements.in --allow-unsafe --strip-extras
	pip-compile -qo dev-requirements.txt dev-requirements.in --allow-unsafe --strip-extras
	pip-compile -qo docs-requirements.txt docs-requirements.in --allow-unsafe --strip-extras
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -qo requirements.txt requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade -qo prod-requirements.txt prod-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade -qo test-requirements.txt test-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade -qo dev-requirements.txt dev-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade -qo docs-requirements.txt docs-requirements.in --allow-unsafe --strip-extras
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt

# To upgrade a specific package to latest version use this command
# make upgrade-package package={package_name}
upgrade-package: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-package:
	pip-compile --upgrade-package $(package) -qo requirements.txt requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade-package $(package) -qo prod-requirements.txt prod-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade-package $(package) -qo test-requirements.txt test-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade-package $(package) -qo dev-requirements.txt dev-requirements.in --allow-unsafe --strip-extras
	pip-compile --upgrade-package $(package) -qo docs-requirements.txt docs-requirements.in --allow-unsafe --strip-extras
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt
