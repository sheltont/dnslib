#!/usr/bin/env bash
nohup python3 -m dnslib.geointerceptresolver --port 53 --log-prefix --upstream 8.8.8.8:53 >./log/inbound.log 2>./log/inbound.log &
