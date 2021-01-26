#!/bin/bash

set -e

echo "installing packaging utilities"
yum install -y zip
amazon-linux-extras install -y python3.8
python3.8 -m pip install --upgrade pip
python3.8 -m pip install virtualenv

echo "creating venv for layer: ${layer_name}"
python3.8 -m venv "${layer_name}"
source "${layer_name}/bin/activate"

echo "installing python layer requirements"
pip install -r /requirements.txt -t ./python
deactivate

echo "creating archive: ${layer_name}.zip"
zip -r "${layer_name}.zip" ./python/

echo "done creating archive; exiting container"
exit