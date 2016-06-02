#!/usr/bin/env bash
nohup python3 -m dnslib.geointerceptresolver --address 172.21.175.241 --port 53 --log-prefix --upstream 8.8.8.8:53 >./log/inbound.log 2>./log/inbound.log &
