#!/bin/bash

unset KUBECONFIG

cd .. && docker build -f Dockerfile \
             -t metaclaw:latest .

docker tag metaclaw:latest metaclaw:$(date +%y%m%d)
