.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	pip-compile -o requirements.txt requirements.in --allow-unsafe
	pip-compile -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile -o dev-requirements.txt dev-requirements.in --allow-unsafe
	pip-compile -o docs-requirements.txt docs-requirements.in --allow-unsafe
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	pip-compile --upgrade -o requirements.txt requirements.in --allow-unsafe
	pip-compile --upgrade -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile --upgrade -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile --upgrade -o dev-requirements.txt dev-requirements.in --allow-unsafe
	pip-compile --upgrade -o docs-requirements.txt docs-requirements.in --allow-unsafe
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt

# To upgrade a specific package to latest version use this command
# make upgrade-package package={package_name}
upgrade-package: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-package:
	pip-compile --upgrade-package $(package) -o requirements.txt requirements.in --allow-unsafe
	pip-compile --upgrade-package $(package) -o prod-requirements.txt prod-requirements.in --allow-unsafe
	pip-compile --upgrade-package $(package) -o test-requirements.txt test-requirements.in --allow-unsafe
	pip-compile --upgrade-package $(package) -o dev-requirements.txt dev-requirements.in --allow-unsafe
	pip-compile --upgrade-package $(package) -o docs-requirements.txt docs-requirements.in --allow-unsafe
	python ../scripts/purge-platform-pkgs.py ./*requirements.txt
