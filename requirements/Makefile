.PHONY: requirements upgrade-requirements

requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
requirements:
	$(info OBSOLETE: Use 'uv add [--dev|--group=GROUP] PACKAGE' to add a new package)

upgrade-requirements: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-requirements:
	$(info OBSOLETE: Use 'uv lock --upgrade' instead)

# To upgrade a specific package to latest version use this command
# make upgrade-package package={package_name}
upgrade-package: export CUSTOM_COMPILE_COMMAND=`make requirements` or `make upgrade-requirements`
upgrade-package:
	$(info OBSOLETE: Use 'uv lock --upgrade-package="$(package)"' instead)
