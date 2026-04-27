#!/bin/bash
#打开日志

cd `dirname $0`/..
export BASE_DIR=`pwd`
echo $BASE_DIR

WORKSPACE_DIR="${METACLAW_WORKSPACE:-$HOME/metaclaw}"
LOG_FILE="${WORKSPACE_DIR}/logs/nohup.out"

if [ ! -f "${LOG_FILE}" ]; then
   echo "No file  ${LOG_FILE}"
   exit -1;
fi

tail -f "${LOG_FILE}"
