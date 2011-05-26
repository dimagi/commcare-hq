#!/usr/bin/bash
# environment variables: remote_host, artifacts, username, password, build_number, version

TARGET_URL="${remote_host}/builds/post/"

curl -v -F "artifacts=@$artifacts" -F "username=$username" -F "password=$password" -F "build_number=$build_number" -F "version=$version" ${TARGET_URL}