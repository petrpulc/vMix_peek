#!/usr/bin/env python3
import argparse
import time
from datetime import timedelta
from xml.etree.ElementTree import fromstring

import requests
import logging


def get_input_active_sources(xml, index):
    def __get_overlays(input):
        visible_inputs = set()
        for overlay in reversed(input.findall("overlay")):
            visible_overlay_layers = __get_layers(inputs_by_key[overlay.attrib['key']])
            visible_inputs.update(visible_overlay_layers)
            if visible_overlay_layers and overlay.find('position') is None:
                break
        return visible_inputs

    def __get_layers(input):
        visible_inputs = __get_overlays(input)
        if input.attrib['type'] not in ('Placeholder', 'Audio'):
            visible_inputs.add(input)
        return visible_inputs

    inputs = list(xml.find('inputs'))
    inputs_by_key = {e.attrib['key']: e for e in inputs}
    inputs_by_index = {e.attrib['number']: e for e in inputs}
    mixes_active = list(e.find('active').text for e in xml.findall('mix'))

    # TODO: assumed mapping for mixes is that earlier created mix is an earlier input, as the id is missing in API
    index_mix_active = dict(zip([e.attrib['number'] for e in inputs if e.attrib['type'] == 'Mix'], mixes_active))

    layers = set()

    input_elem = inputs_by_index[index]
    while input_elem.attrib['type'] == 'Mix':
        layers.update(__get_overlays(input_elem))
        input_elem = inputs_by_index[index_mix_active[index]]

    return __get_layers(input_elem)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--username", required=False)
    parser.add_argument("--password", required=False)
    parser.add_argument("--file", required=False, help="Testing file input")
    parser.add_argument("ip")
    return parser.parse_args()


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


def main(args):
    try:
        while True:
            xml = fromstring(read_api(args))
            get_input_active_sources(xml, '25')
            inputs = list(xml.find('inputs'))
            inputs_by_key = {e.attrib['key']: e for e in inputs}
            inputs_by_index = {e.attrib['number']: e for e in inputs}
            mix_active = list(e.find('active').text for e in xml.findall('mix'))


            live = inputs_by_index[xml.find('active').text]

            print(f"LIVE: {live.attrib['title']}")

            overlays = live.findall("overlay")
            if overlays:
                overlay = inputs_by_key[overlays[-1].attrib['key']]
                if overlay.attrib['type'] == 'GT':
                    print(f"OVERLAY text: {overlay.find('text').text}")

            if live.attrib['type'] == 'VideoList':
                if live.attrib['state'] == 'Running':
                    print('>  ', end='')
                elif live.attrib['state'] == 'Paused':
                    print('|| ', end='')
                print(timedelta(seconds=round(int(live.attrib['position']) / 1000)), end='')
                print(' / ', end='')
                print(timedelta(seconds=round(int(live.attrib['duration']) / 1000)))

            external = inputs.find('input[@title="SLIDES STREAM"]')
            if external:
                external_key = external.findall('overlay')[-1].attrib['key']
                print(f"SLIDES: {inputs[inputs_by_key[external_key]].attrib['title']}")

            audio = [i.attrib['title'] for i in inputs if
                     'audiobusses' in i.attrib and
                     'M' in i.attrib['audiobusses'] and
                     i.attrib['muted'] == 'False' and
                     float(i.attrib['volume']) > 0]
            print(f"AUDIO: {audio}")

            time.sleep(5)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main(parse_args())
