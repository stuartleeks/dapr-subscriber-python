#!/bin/bash
set -e

echo "Installing requirements for subscriber-sdk-direct"
pip install -r src/subscriber-sdk-direct/requirements.txt

echo "Installing requirements for subscriber-sdk-simplified"
pip install -r src/subscriber-sdk-simplified/requirements.txt

echo "\nInstalling requirements for publisher"
pip install -r src/publisher/requirements.txt

