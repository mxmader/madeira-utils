#!/bin/bash

set -e

echo "creating venv for layer: ${package}==${version}"
yum install -y zip
amazon-linux-extras install -y python3.8
python3.8 -m pip install --upgrade pip
python3.8 -m pip install virtualenv
python3.8 -m venv "${package}"
source "${package}/bin/activate"
pip install "${package}==${version}" -t ./python
deactivate
zip -r "${package}.zip" ./python/
exit