#!/usr/bin/env python3
import argparse
import curses
import time
from datetime import timedelta
from xml.etree.ElementTree import fromstring

import requests
import logging


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--username", required=False)
    parser.add_argument("--password", required=False)
    parser.add_argument("--file", required=False, help="Testing file input")
    parser.add_argument("ip")
    return parser.parse_args()


def _trim(text, limit=40):
    if len(text) < limit:
        return text
    else:
        return text[:limit - 3] + '...'


def read_api(args):
    if args.file:
        return ''.join(open(args.file).readlines())

    auth = None
    if args.username:
        auth = (args.username, args.password)
    r = requests.get(f"http://{args.ip}:{args.port}/api", auth=auth)
    if not r.ok:
        logging.error("Unable to read from API")
    return r.content


def main(scr, args):
    try:
        while True:
            xml = fromstring(read_api(args))
            inputs = xml.find('inputs')
            inputs_by_key = {e.attrib['key']: i for i, e in enumerate(inputs)}
            inputs_by_index = {e.attrib['number']: i for i, e in enumerate(inputs)}

            scr.clear()

            live = inputs[inputs_by_index[xml.find('active').text]]
            scr.addstr(f"{_trim(live.attrib['title'])}\n")

            overlays = live.findall("overlay")
            if overlays:
                overlay = inputs[inputs_by_key[overlays[-1].attrib['key']]]
                if overlay.attrib['type'] == 'GT':
                    scr.addstr(f"{_trim(overlay.find('text').text)}\n")

            if live.attrib['type'] == 'VideoList':
                if live.attrib['state'] == 'Running':
                    scr.addstr('>  ')
                elif live.attrib['state'] == 'Paused':
                    scr.addstr('|| ')
                scr.addstr(str(timedelta(seconds=round(int(live.attrib['position']) / 1000))))
                scr.addstr(' / ')
                scr.addstr(str(timedelta(seconds=round(int(live.attrib['duration']) / 1000))))
                scr.addstr('\n')

            external = inputs.find('input[@title="FEED TO APP"]')
            if external:
                external_key = external.findall('overlay')[-1].attrib['key']
                scr.addstr(f"APP: {_trim(inputs[inputs_by_key[external_key]].attrib['title'])}\n")

            audio = [_trim(i.attrib['title']) for i in inputs if
                     'audiobusses' in i.attrib and
                     'M' in i.attrib['audiobusses'] and
                     i.attrib['muted'] == 'False' and
                     float(i.attrib['volume']) > 0]
            scr.addstr(f"AUDIO: {audio}\n")

            scr.refresh()

            time.sleep(5)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    curses.wrapper(main, args=parse_args())
