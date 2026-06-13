#!/bin/bash
set -e

# staging or prod
MODE=$1
WEBSITE_DIR=`pwd`
OUTPUT_DIR=build

# rebuild modules from source
(
  cd ..
  # yarn build
)

# clean up cache
docusaurus clear

case $MODE in
  "prod")
    docusaurus build
    ;;
  "staging")
    STAGING=true docusaurus build
    ;;
esac
