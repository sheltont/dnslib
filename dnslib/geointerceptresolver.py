# -*- coding: utf-8 -*-

"""
    InterceptResolver - proxy requests to upstream server 
                        (optionally intercepting)
        
"""
from __future__ import print_function

import copy
from dnslib.server import DNSServer,DNSHandler,BaseResolver,DNSLogger
from geolite2 import geolite2
import pickle
from dnslib.dns import DNSRecord,DNSQuestion,QTYPE,RR,RCODE,CLASS
import redis

class GeoInterceptResolver(BaseResolver):

    """
        Geo enabled Intercepting resolver
        
        Proxy requests to upstream server optionally intercepting requests
        matching local records
    """

    DEFAULT_LOCATION = 'CN'
    DEFAULT_OVERSEA_OUTBOUND_GATEWAY = '172.21.175.245'
    CN_OVERSEA_OUTBOUND_GATEWAY = '192.168.200.133'

    DEFAULT_TIMEOUT = 5

    def __init__(self,address, port, redis_server, redis_port, skip):
        """
            address/port        - upstream server
            redis_server/port   - redis server
            skip                - list of wildcard labels to skip
        """
        self.address = address
        self.port = port
        self.skip = skip
        self.georeader = geolite2.reader()
        self.cache = redis.StrictRedis(host=redis_server, port=redis_port)

    def resolve(self, request, handler):
        qtype = QTYPE[request.q.qtype]
        qname = request.q.qname
        # We only care about MX requests. For others, just work as a proxy
        if qtype == 'MX':
            if not any([qname.matchGlob(s) for s in self.skip]):
                return self._resolve_mx(request, handler)

        return self._resolve_other(request, handler)

    def _resolve_other(self, request, handler):
        reply = request.reply()
        if not reply.rr:
            if handler.protocol == 'udp':
                proxy_r = request.send(self.address,self.port, tcp=False, timeout=self.DEFAULT_TIMEOUT)
            else:
                proxy_r = request.send(self.address,self.port,tcp=True, timeout=self.DEFAULT_TIMEOUT)
            reply = DNSRecord.parse(proxy_r)
        return reply


    def _resolve_mx(self, request, handler):
        reply = request.reply()
        qname = request.q.qname

        # If we are luck, load the anwer from cache
        rr = self._answer_from_cache(qname)
        if rr:
            a = copy.copy(rr)
            reply.add_answer(a)
            return reply

        # Forward the request to upstream
        reply = self._resolve_other(request, handler)
        if not self._is_noerror(reply):
            return reply

        a = reply.get_a()
        (pref, host) = self._parse_rdata(a.rdata)
        if not self._is_ipaddress(host):
            reply2 = self._resolve_record(host, qtype='A')
            # if we cannot reply MX host to IP address, do nothing
            if not self._is_noerror(reply2):
                return reply
            (pref2, host) = self._parse_rdata(reply2.get_a().rdata)
        loc = self._location_from_client(host)
        gw = self.DEFAULT_OVERSEA_OUTBOUND_GATEWAY
        if loc == 'CN':
            gw = self.CN_OVERSEA_OUTBOUND_GATEWAY

        reply = request.reply()
        zone = "%s\t%s\t%s\t%s\t%s\t%s" % \
                   (qname, a.ttl, CLASS[a.rclass], QTYPE[a.rtype], pref,gw)
        rr = RR.fromZone(zone)[0]
        reply.add_answer(rr)

        # cache the reply
        self._answer_to_cache(qname, reply.get_a())
        return reply



    def _forward_resolve(self, request, handler):
        if handler.protocol == 'udp':
            proxy_r = request.send(self.address, self.port, tcp=False, timeout=self.DEFAULT_TIMEOUT)
        else:
            proxy_r = request.send(self.address, self.port, tcp=True, timeout=self.DEFAULT_TIMEOUT)
        reply = DNSRecord.parse(proxy_r)
        return reply

    def _resolve_record(self, domain, qtype='A'):
        q = DNSRecord(q=DNSQuestion(domain, getattr(QTYPE, qtype)))
        a_pkt = q.send(self.address, self.port, tcp=False)
        reply = DNSRecord.parse(a_pkt)
        return reply

    def _parse_rdata(self, rdata):
        tokens = str(rdata).split(' ')
        if len(tokens) == 2:
            return tokens[0], tokens[1]
        return '', tokens[0]

    def _is_noerror(self, reply):
        return reply.header.rcode == getattr(RCODE, 'NOERROR')

    def _answer_from_cache(self, qname, location=''):
        key = 'mx:%s:%s' % (location, qname)
        val = self.cache.get(key)
        if val:
            rr = pickle.loads(val)
            return rr
        return None

    def _answer_to_cache(self, qname, rr, location=''):
        ttl = rr.ttl
        key = 'mx:%s:%s' % (location, qname)
        val = pickle.dumps(rr)
        self.cache.set(key, val, ttl)


    def _location_from_client(self, ip_address):
        try:
            res = self.georeader.get(ip_address)
            return res['country']['iso_code']
        except:
            return self.DEFAULT_LOCATION

    def _is_ipaddress(self, s):
        try:
            return all(0 <= int(o) <= 255 for o in s.split('.', 3))
        except ValueError:
            pass
        return False

if __name__ == '__main__':

    import argparse,time

    p = argparse.ArgumentParser(description="DNS Intercept Proxy")
    p.add_argument("--port","-p",type=int,default=53,
                    metavar="<port>",
                    help="Local proxy port (default:53)")
    p.add_argument("--address","-a",default="",
                    metavar="<address>",
                    help="Local proxy listen address (default:all)")
    p.add_argument("--redis", "-r", default="localhost:6379",
               metavar="<redis server:port>",
               help="Redis server:port (default:localhost:6379)")
    p.add_argument("--upstream","-u",default="8.8.8.8:53",
            metavar="<dns server:port>",
                    help="Upstream DNS server:port (default:8.8.8.8:53)")
    p.add_argument("--tcp",action='store_true',default=False,
                    help="TCP proxy (default: UDP only)")
    p.add_argument("--skip", "-s", action="append",
                   metavar="<label>",
                   help="Don't intercept matching label (glob)")
    p.add_argument("--log",default="request,reply,truncated,error",
                    help="Log hooks to enable (default: +request,+reply,+truncated,+error,-recv,-send,-data)")
    p.add_argument("--log-prefix",action='store_true',default=False,
                    help="Log prefix (timestamp/handler/resolver) (default: False)")
    args = p.parse_args()

    args.dns,_,args.dns_port = args.upstream.partition(':')
    args.dns_port = int(args.dns_port or 53)

    args.redis,_,args.redis_port = args.redis.partition(':')
    args.redis_port = int(args.redis_port or 6379)

    resolver = GeoInterceptResolver(args.dns,
                                    args.dns_port,
                                    args.redis,
                                    args.redis_port,
                                    args.skip or [])
    logger = DNSLogger(args.log,args.log_prefix)

    print("Starting Intercept Proxy (%s:%d -> %s:%d) [%s]" % (
                        args.address or "*",args.port,
                        args.dns,args.dns_port,
                        "UDP/TCP" if args.tcp else "UDP"))
    DNSHandler.log = { 
        'log_request',      # DNS Request
        'log_reply',        # DNS Response
        'log_truncated',    # Truncated
        'log_error',        # Decoding error
    }

    udp_server = DNSServer(resolver,
                           port=args.port,
                           address=args.address,
                           logger=logger)
    udp_server.start_thread()

    if args.tcp:
        tcp_server = DNSServer(resolver,
                               port=args.port,
                               address=args.address,
                               tcp=True,
                               logger=logger)
        tcp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)

