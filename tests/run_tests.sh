#!/usr/bin/env bash

# Run the test suite.
python2 -m unittest discover -v &&
python3 -m unittest discover -v
