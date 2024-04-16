#!/usr/bin/python3

import subprocess
import json
import requests
import re
import sys
import argparse
import time

def get_relays():
    try:
        relays={
            val["desc"]:[relay["ipv4"] for relay in val["relays"]]
            for (key, val)
            in json.loads(
                requests.get(
                    "https://api.steampowered.com/ISteamApps/GetSDRConfig/v1/?appid=730"
                ).content)["pops"].items()
            if "relays" in val
            and "desc" in val
        }
    except requests.exceptions.SSLError as e:
        print("connection insecure. aborting", file=sys.stderr)
        sys.exit(-1)
    return relays

def list():
    print("\n".join(get_relays().keys()))

def select(countries):
    relays=get_relays()
        
    # subprocess.run is system(), always validate system()
    # re is not the best test but good enough who cares tbh
    test = re.compile(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$")
    for (relay, ips) in relays.items():
        for ip in ips:
            if test.fullmatch(ip) is None:
                print("got some garbage, not ip: %s. bailing out." % ip, file=sys.stderr)
                sys.exit(-2)
            
    if 0 != subprocess.run(("sudo ipset -! create cs2_mm_relays hash:ip").split()).returncode:
        print("something broke creating ipsets, youre on your own", file=sys.stderr)
        sys.exit(-3)

    if 0 != subprocess.run(("sudo iptables -I INPUT -m set --match-set cs2_mm_relays src,dst -j DROP").split()).returncode:
        print("something broke blocking set, youre on your own", file=sys.stderr)
        sys.exit(-4)

    for (relay, ips) in relays.items():
        if not any([country.lower() in relay.lower() for country in countries]):
            for ip in ips:
                if 0 != subprocess.run(("sudo ipset -! add cs2_mm_relays %s" % ip).split()).returncode:
                    print("ip: %s" % (ip), file=sys.stderr)
                    print("something broke adding ip to set, youre on your own.", file=sys.stderr)
                    sys.exit(-5)

def unblock():
    with open("/dev/null") as null:
        # vulnerable to toctou but who cares
        if 0 == subprocess.run(("sudo iptables -C INPUT -m set --match-set cs2_mm_relays src,dst -j DROP").split(), stderr=null).returncode:
            if 0 != subprocess.run(("sudo iptables -D INPUT -m set --match-set cs2_mm_relays src,dst -j DROP").split()).returncode:
                print("something broke unblocking set, youre on your own", file=sys.stderr)
                sys.exit(-6)

    # workaround a bug in iptables, it returns before the change is fully commited
    time.sleep(0.1)

    if 0 != subprocess.run(("sudo ipset destroy cs2_mm_relays").split()).returncode:
        print("something broke destroying set, youre on your own.", file=sys.stderr)
        sys.exit(-7)

def main(argv):
    parser = argparse.ArgumentParser(description=
        "this application allows you to select the steam relays "
        "on which you want to play for the game counter strike. "
        "sudo as root is required to block the ip "
        "addresses of the relays.",
        prog = "match making server selector"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--select',
        nargs="+",
        help=
            "list of relays not to block. matching is done by a "
            "case insensitive substring match, e.g. \"sweden\" "
            "matches both Stockholm - Kista (Sweden) and "
            "Stockholm - Bromma (Sweden)",
        metavar="COUNTRY"
    )
    group.add_argument(
        '--unblock',
        action='store_const',
        help='unblocks all relays',
        const=True,
        default=False,
    )
    group.add_argument(
        '--list',
        action='store_const',
        const=True,
        default=False,
        help='list all relays',
    )
    args = vars(parser.parse_args())

    if args["list"]:
        list()
    elif args["unblock"]:
        unblock()
    elif args["select"]:
        select(args["select"])

main(sys.argv)
