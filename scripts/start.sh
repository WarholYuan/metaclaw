#!/bin/bash
# 后台运行 MetaClaw 执行脚本

cd `dirname $0`/..
export BASE_DIR=`pwd`
echo $BASE_DIR

WORKSPACE_DIR="${METACLAW_WORKSPACE:-$HOME/metaclaw}"
LOG_DIR="${WORKSPACE_DIR}/logs"
LOG_FILE="${LOG_DIR}/nohup.out"
mkdir -p "${LOG_DIR}"

nohup python3 "${BASE_DIR}/app.py" > "${LOG_FILE}" 2>&1 & tail -f "${LOG_FILE}"

echo "MetaClaw is starting, you can check ${LOG_FILE}"
