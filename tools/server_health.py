"""Fixed read-only host probes; private authenticated HTTP for n8n only."""
import argparse
import csv
import math
import concurrent.futures
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlencode
from performance_metrics import PerformanceSampler

SERVICES = ('Jellyfin','Radarr','Sonarr','Prowlarr','SABnzbd','qBittorrent','n8n')
log = logging.getLogger('snake_health')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def valid_sample(status, headers, body):
    headers = {k.lower(): v for k, v in headers.items()}
    match = re.fullmatch(r'bytes 0-4095/([0-9]+)', headers.get('content-range',''))
    return (status == 206 and match is not None and int(match[1]) >= 4096
            and len(body) == 4096 and headers.get('content-type','').split(';')[0]
            in {'video/mp4','video/x-matroska','video/webm','video/mp2t','application/octet-stream','video/x-msvideo','video/mpeg','video/quicktime'})


def fetch(url, headers=None, sample=False, json_response=True):
    req = urllib.request.Request(url, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=4) as response:
        body = response.read(4097 if sample else 1048577)
        if sample:
            return valid_sample(response.status, dict(response.headers), body)
        if len(body)>1048576:
            raise ValueError('response_too_large')
        return json.loads(body) if json_response else bool(body)


def service_probe(config, name):
    try:
        entry=config['services'][name]
        fetch(entry['url'],entry.get('headers',{}),json_response=entry.get('json',True))
        return True
    except Exception as error:
        log.warning('Service probe failed service=%s error_type=%s',name,type(error).__name__)
        return False


def playback_probe(config):
    base=config['jellyfin']['url'].rstrip('/')
    headers=config['jellyfin']['headers']
    result={'active':None,'sample':'failed'}
    try:
        sessions=fetch(base+'/Sessions',headers)
        if not isinstance(sessions,list): raise ValueError('sessions_invalid')
        result['active']=sum(bool(s.get('NowPlayingItem')) for s in sessions)
    except Exception as error:
        log.warning('Playback session probe failed error_type=%s',type(error).__name__)
    try:
        data=fetch(base+'/Items?'+urlencode({'Recursive':'true','IncludeItemTypes':'Movie,Episode','Fields':'MediaSources','Limit':'10','IsVirtualItem':'false'}),headers)
        items=data.get('Items')
        if not isinstance(items,list): raise ValueError('library_invalid')
        candidates=[(item,source) for item in items for source in item.get('MediaSources',[]) if source.get('Protocol')=='File' and source.get('Type')!='Placeholder']
        if not candidates:
            result['sample']='no_media'
            return result
        item,source=candidates[0]
        if not all(re.fullmatch(r'[a-fA-F0-9]{32}',str(x)) for x in (item.get('Id'),source.get('Id'))):
            raise ValueError('invalid_sample_id')
        url=base+'/Videos/'+item['Id']+'/stream?'+urlencode({'Static':'true','MediaSourceId':source['Id']})
        if fetch(url,dict(headers,Range='bytes=0-4095'),sample=True):
            result['sample']='ok'
    except Exception as error:
        log.warning('Playback sample failed error_type=%s',type(error).__name__)
    return result


def storage_probe():
    rows=[]
    for label,path in [('Main','/mnt/media'),('SSD','/mnt/media-overflow'),('Pool','/mnt/media-pool')]:
        try:
            output=subprocess.check_output(['df','-B1','--output=size,avail',path],timeout=3,text=True)
            total,free=map(int,output.splitlines()[-1].split())
            rows.append({'label':label,'totalGiB':total/1024**3,'freeGiB':free/1024**3})
        except Exception:
            rows.append({'label':label,'totalGiB':None,'freeGiB':None})
    try:
        check=subprocess.run(['/usr/local/sbin/snake-storage-check'],capture_output=True,timeout=4)
        guard=check.returncode==0
    except Exception:
        guard=False
    return {'guard':guard,'disks':rows}


def parse_gpu(output):
    row = next(csv.reader(output.strip().splitlines()))
    if len(row) not in (4,7): raise ValueError('gpu_invalid')
    name = row[0].strip()
    utilization, used, total = map(float, row[1:4])
    if not re.fullmatch(r'[A-Za-z0-9 ()._-]{1,100}', name) or not all(math.isfinite(n) for n in (utilization, used, total)) or not 0 <= utilization <= 100 or not 0 <= used <= total or total <= 0:
        raise ValueError('gpu_invalid')
    def optional(index, maximum):
        try:
            value=float(row[index])
            return value if math.isfinite(value) and 0<=value<=maximum else None
        except (IndexError,ValueError):return None
    return {'available':True,'name':name,'utilizationPercent':utilization,'memoryUsedMiB':used,'memoryTotalMiB':total,
        'temperatureC':optional(4,150),'encoderPercent':optional(5,100),'decoderPercent':optional(6,100)}


def gpu_probe():
    try:
        try:
            output = subprocess.check_output(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,utilization.encoder,utilization.decoder','--format=csv,noheader,nounits'], timeout=3, text=True,stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            output = subprocess.check_output(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'], timeout=3, text=True,stderr=subprocess.DEVNULL)
        return parse_gpu(output)
    except Exception:
        return {'available':False}


def upload_rate(before, after, seconds):
    if not all(math.isfinite(n) for n in (before,after,seconds)) or before < 0 or after < before or seconds <= 0:
        raise ValueError('network_sample_invalid')
    return (after-before)*8/seconds/1000000


def collect(config):
    start=int(time.time()*1000)
    mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
    host={'load1':os.getloadavg()[0],'cores':os.cpu_count(),'memoryUsed':(mem['MemTotal']-mem['MemAvailable'])/1024**3,'memoryTotal':mem['MemTotal']/1024**3,'uptimeHours':float(Path('/proc/uptime').read_text().split()[0])/3600}
    with concurrent.futures.ThreadPoolExecutor(max_workers=11) as pool:
        service={s:pool.submit(service_probe,config,s) for s in SERVICES}
        playback=pool.submit(playback_probe,config)
        storage=pool.submit(storage_probe)
        gpu=pool.submit(gpu_probe)
        return {'version':1,'checkedAt':start,'host':host,'storage':storage.result(),'services':{s:f.result() for s,f in service.items()},'playback':playback.result(),'gpu':gpu.result()}


class Collector:
    def __init__(self,config):
        self.config=config;self.lock=threading.Lock();self.cached=None;self.when=0
        self.performance=PerformanceSampler();self.performance.start()

    def read(self):
        with self.lock:
            if self.cached is None or time.monotonic()-self.when>=60:
                self.cached=collect(self.config);self.when=time.monotonic()
            readings=self.performance.snapshot()
            return {**self.cached,'host':{**self.cached['host'],'cpu':readings['cpu']},'network':readings['network']}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    def do_GET(self):
        if self.path!='/health' or not hmac.compare_digest(self.headers.get('X-Snake-Media-Key','').encode(),self.server.collector.config['secret'].encode()):
            self.send_error(403);return
        try:
            data=self.server.collector.read();status=200
        except Exception as error:
            log.error('Host collection failed error_type=%s',type(error).__name__)
            data={'version':1,'unavailable':True};status=503
        body=json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);args=parser.parse_args()
    if args.config.stat().st_mode&0o077: raise ValueError('private_config_required')
    config=json.loads(args.config.read_text())
    if len(config['secret'])<24: raise ValueError('strong_shared_secret_required')
    import ipaddress
    ip=ipaddress.ip_address(config['bind'])
    if ip not in ipaddress.ip_network('172.16.0.0/12'): raise ValueError('docker_gateway_bind_required')
    server=ThreadingHTTPServer((config['bind'],config.get('port',17492)),Handler);server.collector=Collector(config);server.serve_forever()


if __name__=='__main__': main()
