#!/bin/bash
set -e

echo "Installing requirements for subscriber"
pip install -r src/subscriber/requirements.txt

echo "\nInstalling requirements for publisher"
pip install -r src/publisher/requirements.txt


# echo -e "\nInitialising dapr"
# dapr init
