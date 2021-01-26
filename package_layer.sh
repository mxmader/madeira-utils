#!/bin/bash

package="${1}"
version="${2}"
container="${package}_layer"

docker run --name "${container}" -it \
  -e package="${package}" \
  -e version="${version}" \
  -v $PWD/create_layer.sh:/create_layer.sh \
  amazonlinux:2.0.20191016.0 \
  ./create_layer.sh

# back in local machine user shell
echo "copying layer ZIP from container"
docker cp "${container}:${package}.zip" layers/

echo "deleting container"
docker rm "${container}"
