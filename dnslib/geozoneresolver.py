# -*- coding: utf-8 -*-

from __future__ import print_function

import copy
from os import listdir
from os.path import isfile, join, isdir, dirname

from dnslib import RR,QTYPE,RCODE
from dnslib.server import DNSServer,DNSHandler,BaseResolver,DNSLogger
from dnslib.zoneresolver import ZoneResolver
from geolite2 import geolite2


class GeoZoneResolver(BaseResolver):
    """
        Geo-enabled fixed zone file resolver.
    """

    DEFAULT_LOCATION = 'DEFAULT'

    def __init__(self, zonedir, glob=False):
        self.georeader = geolite2.reader()

        self.zones = {}
        """
            Initialise resolver from zone file directory.
            GEO location information is extracted from file name suffix
            e.g: "oversea.ceair.com-CN", this is a zone file for all CN client ip
        """
        zone_files = [f for f in listdir(zonedir) if isfile(join(zonedir, f))]
        for file in zone_files:
            location = self._location_from_suffix(file)
            full_path = join(zonedir, file)
            print("Processing zone file: %s" % full_path)
            zone = open(full_path)
            self.zones[location] = ZoneResolver(zone, glob)
        self.glob = glob
        self.eq = 'matchGlob' if glob else '__eq__'

    def resolve(self, request, handler):
        """
            Respond to DNS request - parameters are request packet & handler.
            Method is expected to return DNS response
        """

        location = self._location_from_client(handler.client_address)
        zone_resolver = self._zoneresolver_from_location(location)
        return zone_resolver.resolve(request, handler)

    def _location_from_suffix(self, filename):
        tokens = filename.split('-')
        if len(tokens) == 2:
            return tokens[-1].upper()
        return self.DEFAULT_LOCATION

    def _location_from_client(self, ip_address):
        try:
            (ip, port) = ip_address
            res = self.georeader.get(ip)
            return res['country']['iso_code']
        except:
            return self.DEFAULT_LOCATION

    def _zoneresolver_from_location(self, location):
        if location in self.zones:
            return self.zones[location]
        return self.zones[self.DEFAULT_LOCATION]


if __name__ == '__main__':

    import argparse, time

    p = argparse.ArgumentParser(description="GEO Zone DNS Resolver")
    p.add_argument("--zonedir","-z",required=True,
                        metavar="<zone-file>",
                        help="Zone file directory")
    p.add_argument("--port","-p",type=int,default=53,
                        metavar="<port>",
                        help="Server port (default:53)")
    p.add_argument("--address","-a",default="",
                        metavar="<address>",
                        help="Listen address (default:all)")
    p.add_argument("--glob",action='store_true',default=False,
                        help="Glob match against zone file (default: false)")
    p.add_argument("--udplen","-u",type=int,default=0,
                    metavar="<udplen>",
                    help="Max UDP packet length (default:0)")
    p.add_argument("--tcp",action='store_true',default=False,
                        help="TCP server (default: UDP only)")
    p.add_argument("--log",default="request,reply,truncated,error",
                    help="Log hooks to enable (default: +request,+reply,+truncated,+error,-recv,-send,-data)")
    p.add_argument("--log-prefix",action='store_true',default=False,
                    help="Log prefix (timestamp/handler/resolver) (default: False)")
    args = p.parse_args()


    if isdir(args.zonedir):
        args.zonedir = args.zonedir
    else:
        script_dir = dirname(__file__)
        args.zonedir = join(script_dir, args.zonedir)

    resolver = GeoZoneResolver(args.zonedir,args.glob)
    logger = DNSLogger(args.log, args.log_prefix)

    print("Starting Geo Zone Resolver (%s:%d) [%s]" % (
                        args.address or "*",
                        args.port,
                        "UDP/TCP" if args.tcp else "UDP"))

    for zone_resolver in resolver.zones.values():
        for rr in zone_resolver.zone:
            print("    | ", rr[2].toZone(), sep="")
        print()

    if args.udplen:
        DNSHandler.udplen = args.udplen

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

