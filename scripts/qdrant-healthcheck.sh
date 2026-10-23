#!/bin/bash
set -eu
exec 3<>/dev/tcp/127.0.0.1/6333
printf 'GET /readyz HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' >&3
IFS=' ' read -r -t 2 protocol status remainder <&3
[[ "$protocol" == HTTP/* && "$status" == 200 ]]
