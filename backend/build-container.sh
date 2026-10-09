#!/bin/bash

# Check if exactly two arguments are supplied
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <tag> <registry>"
  exit 1
fi

TAG=$1
REGISTRY=$2

docker build -t "$TAG" . &&
  docker login "$REGISTRY" &&
  docker tag "$TAG" "${REGISTRY}/${TAG}:latest" &&
  docker push "${REGISTRY}/${TAG}:latest"
