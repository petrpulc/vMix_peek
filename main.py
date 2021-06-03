#!/usr/bin/env python3
import argparse
import curses
import time
from datetime import timedelta
from xml.etree.ElementTree import fromstring

import requests


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--username", required=False)
    parser.add_argument("--password", required=False)
    parser.add_argument("ip")
    return parser.parse_args()


def main(scr, args):
    auth = None
    if args.username:
        auth = (args.username, args.password)

    try:
        while True:
            r = requests.get(f"http://{args.ip}:{args.port}/api", auth=auth)
            if not r.ok:
                break
            xml = fromstring(r.content)
            inputs = xml.find('inputs')
            inputs_by_key = {e.attrib['key']: i for i, e in enumerate(inputs)}
            inputs_by_index = {e.attrib['number']: i for i, e in enumerate(inputs)}

            live = inputs[inputs_by_index[xml.find('active').text]]

            scr.clear()
            scr.addstr(f"{live.attrib['title']}\n")

            overlays = live.findall("overlay")
            if overlays:
                overlay = inputs[inputs_by_key[overlays[-1].attrib['key']]]
                if overlay.attrib['type'] == 'GT':
                    scr.addstr(f"{overlay.find('text').text}\n")

            if live.attrib['type'] == 'VideoList':
                if live.attrib['state'] == 'Running':
                    scr.addstr('>  ')
                elif live.attrib['state'] == 'Paused':
                    scr.addstr('|| ')
                scr.addstr(str(timedelta(seconds=round(int(live.attrib['position']) / 1000))))
                scr.addstr(' / ')
                scr.addstr(str(timedelta(seconds=round(int(live.attrib['duration']) / 1000))))
                scr.addstr('\n')

            external = inputs.find('input[@title="EXTERNAL"]')
            if external:
                external_key = external.findall('overlay')[-1].attrib['key']
                scr.addstr(f"EXTERNAL: {inputs[inputs_by_key[external_key]].attrib['title']}\n")

            audio = [i.attrib['title'] for i in inputs if
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
