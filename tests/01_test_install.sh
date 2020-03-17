#!/bin/bash

echo "Running notectl installation test..."


docker run --volumes-from jenkins --rm --entrypoint $WORKSPACE/notectl/test-entrypoint.sh python:3.8