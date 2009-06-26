#!/usr/bin/env python

import os
import sys
import socket
import time

from esxsnmp.util import get_ESDB_client

def gen_ma_storefile():
    """Translated from the original Perl by jdugan"""
    params = {}
    params['hostname'] = socket.gethostname()
    params['date'] = time.asctime()
    params['user'] = os.getlogin()
    params['args'] = " ".join(sys.argv)

    debug = False

    AUTHREALM = "ESnet-Public"
    DOMAIN = "es.net"
    HEADER = """<?xml version="1.0" encoding="UTF-8"?>


<!-- ===================================================================
<description>
   MA RRD configuration file

   $Id$
   project: perfSONAR

Notes:
   This is the configuration file which contains the information 
   about RRD files from ESnet.

   It was generated by %(user)s on %(hostname)s using %(args)s
   at %(date)s


    -Joe Metzger


</description>
==================================================================== -->
<nmwg:store
         xmlns:nmwg="http://ggf.org/ns/nmwg/base/2.0/"
         xmlns:netutil="http://ggf.org/ns/nmwg/characteristic/utilization/2.0/"
         xmlns:nmwgt="http://ggf.org/ns/nmwg/topology/2.0/" 
         xmlns:nmwgt3="http://ggf.org/ns/nmwg/topology/3.0/" >

     <!-- Note: The URNs and the nmwgt3 namespace are possible implementations, and not standard.
          The URNs should not be meta-data IDs. But maybe they should be idRefs. But this seems
          to be expanding the scope of a reference significantly...  Joe
      -->

     <!--  metadata section  -->

""" % params


    bogusIP = "BOGUS1"

    print HEADER

    (transport, client) = get_ESDB_client(server='snmp-west.es.net', port=9090)
    transport.open()

    oidset_rtr_map = {}
    interfaces = []

    for device in client.list_devices(1):
        if debug:
            print >>sys.stderr, "starting %s" % device

        for iface in client.get_interfaces(device, 0):
            if iface.ipaddr:
                try:
                    iface.dns = socket.gethostbyaddr(iface.ipaddr)[0]
                except socket.herror:
                    iface.dns = ''
            else:
                iface.dns = ''

            try:
                oidset = oidset_rtr_map[iface.device.name]
            except KeyError:
                for oidset in iface.device.oidsets:
                    if oidset.name == 'FastPoll':
                        oidset_rtr_map[iface.device.name] = oidset
                        break
                    elif oidset.name == 'FastPollHC':
                        oidset_rtr_map[iface.device.name] = oidset
                        break
      
            if oidset.name == 'FastPollHC':
                prefix = 'ifHC'
            elif oidset.name == 'FastPoll':
                prefix = 'if'
            else:
                print "<!-- No OIDSet for %s %s -->" % (iface.device.name,
                        iface.ifdescr)
                print >>sys.stderr, "No OIDSet for %s %s: %s" % (iface.device.name,
                        iface.ifdescr, ",".join([o.name for o in iface.device.oidsets]))

            iface.intpath = iface.ifdescr;
            iface.intpath = iface.intpath.replace("/","_")
            iface.intpath = iface.intpath.replace(" ","_")
            iface.key = '%s:%s' % (iface.device.name, iface.ifdescr)

            rtr = iface.device.name
            
            if iface.ifhighspeed == 0:
                speed = iface.ifspeed
            else:
                speed = iface.ifhighspeed * int(1e6)

            d = dict(
                    intname=iface.ifdescr,
                    namein='%s/%s/%sInOctets/%s' % (rtr, oidset.name, prefix,
                        iface.intpath),
                    nameout='%s/%s/%sOutOctets/%s' % (rtr, oidset.name, prefix,
                        iface.intpath),
                    intdesc=iface.ifalias,
                    device=rtr,
                    dns=iface.dns,
                    speed=speed,
                    ipaddr=iface.ipaddr,
                    domain=DOMAIN,
                    authrealm=AUTHREALM)

            interfaces.append(d)

        if debug:
            print >>sys.stderr, "done with %s" % (device)

    #
    # Now need to generate XML name spaces/rnc info
    #

    META = [] # Contains the Meta Data
    DATA = [] # Contains the data

    i = 0

    for iface in interfaces:
        if not iface['intname']:
            continue

        if iface['ipaddr']:
            iface['ipaddr_line'] = """
\t\t\t\t<nmwgt:ifAddress type="ipv4">%s</nmwgt:ifAddress>""" % iface['ipaddr']
        else:
            iface['ipaddr_line'] = ''

        for dir in ('in', 'out'):
            i += 1
            iface['i'] = i
            iface['dir'] = dir
            if dir == 'in':
                iface['name'] = iface['namein']
            else:
                iface['name'] = iface['nameout']

            m = """
\t<nmwg:metadata  xmlns:nmwg="http://ggf.org/ns/nmwg/base/2.0/" id="meta%(i)d">
\t\t<netutil:subject  xmlns:netutil="http://ggf.org/ns/nmwg/characteristic/utilization/2.0/" id="subj%(i)d">
\t\t\t<nmwgt:interface xmlns:nmwgt="http://ggf.org/ns/nmwg/topology/2.0/">
\t\t\t\t<nmwgt3:urn xmlns:nmwgt3="http://ggf.org/ns/nmwg/topology/base/3.0/">urn:ogf:network:domain=%(domain)s:node=%(device)s:port=%(intname)s</nmwgt3:urn>%(ipaddr_line)s
\t\t\t\t<nmwgt:hostName>%(device)s</nmwgt:hostName>
\t\t\t\t<nmwgt:ifName>%(intname)s</nmwgt:ifName>
\t\t\t\t<nmwgt:ifDescription>%(intdesc)s</nmwgt:ifDescription>
\t\t\t\t<nmwgt:capacity>%(speed)s</nmwgt:capacity>
\t\t\t\t<nmwgt:direction>%(dir)s</nmwgt:direction>
\t\t\t\t<nmwgt:authRealm>%(authrealm)s</nmwgt:authRealm>
\t\t\t</nmwgt:interface>
\t\t</netutil:subject>
\t\t<nmwg:eventType>http://ggf.org/ns/nmwg/characteristic/utilization/2.0</nmwg:eventType>
\t\t<nmwg:parameters id="metaparam%(i)d">
\t\t\t<nmwg:parameter name="supportedEventType">http://ggf.org/ns/nmwg/characteristic/utilization/2.0</nmwg:parameter>
\t\t\t<nmwg:parameter name="supportedEventType">http://ggf.org/ns/nmwg/tools/snmp/2.0</nmwg:parameter>
\t\t</nmwg:parameters>
\t</nmwg:metadata>""" % iface

            META.append(m)

            d = """
\t<nmwg:data  xmlns:nmwg="http://ggf.org/ns/nmwg/base/2.0/" id="data%(i)d" metadataIdRef="meta%(i)d">
\t\t<nmwg:key id="keyid%(i)d">
\t\t\t<nmwg:parameters id="dataparam%(i)d">
\t\t\t\t<nmwg:parameter name="type">esxsnmp</nmwg:parameter>
\t\t\t\t<nmwg:parameter name="valueUnits">Bps</nmwg:parameter>
\t\t\t\t<nmwg:parameter name="name">%(name)s</nmwg:parameter>
\t\t\t\t<nmwg:parameter name="eventType">http://ggf.org/ns/nmwg/characteristic/utilization/2.0</nmwg:parameter>
\t\t\t</nmwg:parameters>
\t\t</nmwg:key>
\t</nmwg:data>""" % iface

            DATA.append(d)



    print ''.join(META)
    print ''.join(DATA)
    print '</nmwg:store>'
            
