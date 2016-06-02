#!/usr/bin/env bash
nohup python3 -m dnslib.geozoneresolver --address 172.21.175.241 --port 53 --log-prefix --zonedir ./data/zone/oversea.ceair.com >./log/inbound.log 2>./log/inbound.log &
