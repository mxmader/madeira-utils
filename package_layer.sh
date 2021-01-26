#!/bin/bash

set -e

layer_requirements_path="${PWD}/layer_requirements.txt"

if [ ! -f "${layer_requirements_path}" ]; then
  echo "${layer_requirements_path} does not exist or is not a file"
  exit 1
fi

layer_name="${1}"
destination_path="layers/"
container="layer-packaging-$(uuid)"
base_dir=$(cd "$(dirname "$0")"; pwd)

docker run --name "${container}" -it \
  -e layer_name="${layer_name}" \
  -v "${layer_requirements_path}":/requirements.txt \
  -v "${base_dir}/create_layer.sh":/create_layer.sh \
  amazonlinux:2.0.20191016.0 \
  ./create_layer.sh

# back in local machine user shell
echo "copying layer ZIP from container"
mkdir -p "${destination_path}"
docker cp "${container}:${layer_name}.zip" "${destination_path}"

echo "deleting container"
docker rm "${container}"
