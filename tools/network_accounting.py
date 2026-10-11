"""Count physical-interface egress by destination; never inspect packet contents."""
import argparse
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import uuid

TABLE = 'snake_upload_metrics'
CATEGORIES = ('lan', 'internet', 'other')
LOCAL4 = ('169.254.0.0/16', '224.0.0.0/4', '255.255.255.255/32')
LOCAL6 = ('fe80::/10', 'ff00::/8')
# Conservative exclusions: reserved/private destinations are never called internet.
RESERVED4 = ('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8',
    '169.254.0.0/16','172.16.0.0/12','192.0.0.0/24','192.0.2.0/24',
    '192.168.0.0/16','198.18.0.0/15','198.51.100.0/24','203.0.113.0/24',
    '224.0.0.0/4','240.0.0.0/4')
RESERVED6 = ('2001::/23', '2001:db8::/32', '2002::/16', '3fff::/20')


def networks(prefixes, version):
    values = [ipaddress.ip_network(p, strict=False) for p in prefixes]
    if any(n.prefixlen == 0 for n in values):
        raise ValueError('default_is_not_lan')
    return [str(n) for n in ipaddress.collapse_addresses(n for n in values if n.version == version)]


def classify(address, prefixes):
    ip = ipaddress.ip_address(address)
    local = prefixes + list(LOCAL4 if ip.version == 4 else LOCAL6)
    if any(ip in ipaddress.ip_network(p, strict=False) for p in local):
        return 'lan'
    reserved = RESERVED4 if ip.version == 4 else RESERVED6
    if ip.version == 6 and ip not in ipaddress.ip_network('2000::/3'):
        return 'other'
    return 'other' if any(ip in ipaddress.ip_network(p) for p in reserved) else 'internet'


def rules(topology, replace=False):
    if not topology or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', n) for n in topology):
        raise ValueError('invalid_physical_interfaces')
    out = [f'delete table netdev {TABLE}'] if replace else []
    out += [f'table netdev {TABLE} {{']
    out += [f' counter {k} {{ }}' for k in CATEGORIES]
    for index, (name, prefixes) in enumerate(sorted(topology.items())):
        out += [f' chain tx_{index} {{',f'  type filter hook egress device "{name}" priority 0; policy accept;']
        for version, local in [(4, LOCAL4), (6, LOCAL6)]:
            family = 'ip' if version == 4 else 'ip6'
            ns = ', '.join(networks(list(prefixes)+list(local), version))
            out.append(f'  {family} daddr {{ {ns} }} counter name lan return')
        out += [f'  ip daddr != {{ {", ".join(RESERVED4)} }} counter name internet return',
                f'  ip6 daddr 2000::/3 ip6 daddr != {{ {", ".join(RESERVED6)} }} counter name internet return',
                '  counter name other', ' }']
    return '\n'.join(out + ['}']) + '\n'


def command(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=5, **kw).stdout


def topology():
    root = Path('/sys/class/net')
    names = sorted(p.name for p in root.iterdir() if (p/'device').exists()
        and (p/'operstate').read_text().strip() == 'up')
    routes = json.loads(command(['ip','-j','route','show'])) + json.loads(command(['ip','-j','-6','route','show']))
    return {name: sorted({r['dst'] for r in routes if r.get('dev') == name
        and r.get('dst') != 'default' and not r.get('gateway') and r.get('type','unicast') == 'unicast'})
        for name in names}


def parse_counters(data):
    result = {}
    for entry in data['nftables']:
        c = entry.get('counter')
        if not c:
            continue
        if c.get('family') != 'netdev' or c.get('table') != TABLE:
            raise ValueError('unexpected_table')
        name, count = c.get('name'), c.get('bytes')
        if name not in CATEGORIES or name in result or type(count) is not int or not 0 <= count < 2**64:
            raise ValueError('invalid_counter')
        result[name] = count
    if set(result) != set(CATEGORIES):
        raise ValueError('missing_counter')
    return result


def install(current):
    exists = subprocess.run(['nft','list','table','netdev',TABLE],capture_output=True,timeout=5).returncode == 0
    text = rules(current, exists)
    command(['nft','--check','-f','-'], input=text)
    command(['nft','-f','-'], input=text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/run/snake-network/counters.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    current = topology()
    if args.check:
        exists = subprocess.run(['nft','list','table','netdev',TABLE],capture_output=True,timeout=5).returncode == 0
        command(['nft','--check','-f','-'],input=rules(current,exists))
        print('Counter rules validated')
        return
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generation = None
    configured = None
    next_topology = 0
    while not stop.is_set():
        try:
            if time.monotonic() >= next_topology:
                current = topology(); next_topology = time.monotonic()+60
            if current != configured:
                install(current); configured = current; generation = str(uuid.uuid4())
            data = json.loads(command(['nft','-j','list','table','netdev',TABLE]))
            counters = parse_counters(data)
            value = dict(version=1,generation=generation,sampledAt=time.time(),counters=counters)
            tmp = args.output.with_suffix('.tmp')
            tmp.write_text(json.dumps(value)); tmp.chmod(0o644); os.replace(tmp,args.output)
        except Exception as error:
            logging.warning('Accounting unavailable error_type=%s',type(error).__name__)
            configured = None
            # No fresh data is published; consumers expire the last sample.
        stop.wait(2)


if __name__ == '__main__':
    main()
