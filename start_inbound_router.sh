#!/usr/bin/env bash
nohup python3 -m dnslib.geozoneresolver --port 53 --log-prefix --zonedir ./data/zone/oversea.ceair.com >../log/inbound.log 2>../log/inbound.log &&