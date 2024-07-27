from dataclasses import dataclass
from xml.etree.ElementTree import Element


@dataclass(frozen=True)
class Input:
    input: Element
    layers: set[Element]


class VMixDTO:
    @staticmethod
    def __get_inputs_with_layers(xml: Element) -> list[Input]:
        def __get_visible(input_elem) -> set[Element]:
            visible_inputs = {input_elem}
            if input_elem.attrib['type'] == 'Mix':
                visible_inputs.update(__get_visible(inputs_by_index[index_mix_active[input_elem.attrib['number']]]))
            for overlay in input_elem.findall('overlay'):
                visible_inputs.update(__get_visible(inputs_by_key[overlay.attrib['key']]))
            return visible_inputs

        original_inputs = list(xml.find('inputs'))
        inputs_by_index = {e.attrib['number']: e for e in original_inputs}
        inputs_by_key = {e.attrib['key']: e for e in original_inputs}
        mixes_active = list(e.find('active').text for e in xml.findall('mix'))
        index_mix_active = dict(
            zip([e.attrib['number'] for e in original_inputs if e.attrib['type'] == 'Mix'], mixes_active))

        inputs = []
        for input_elem in original_inputs:
            inputs.append(Input(
                input_elem,
                __get_visible(input_elem)
            ))
        return inputs

    def __init__(self, xml: Element) -> None:
        self.stream_cam = set()
        self.stream_slides = set()
        self.venue = set()
        self.captions = False
        self.audio_master_inputs = list()
        self.audio_master = dict()

        self.recording = False
        self.streaming = dict()

        inputs = self.__get_inputs_with_layers(xml)
        inputs_by_index = {e.input.attrib['number']: e for e in inputs}
        inputs_by_title = {e.input.attrib['title']: e for e in inputs}

        try:
            self.stream_cam = set(l.attrib['title'] for l in inputs_by_index[xml.find('active').text].layers)
            self.stream_slides = set(l.attrib['title'] for l in inputs_by_title['SLIDES STREAM'].layers)
            self.venue = set(l.attrib['title'] for l in inputs_by_title['FEED TO VENUE'].layers)

            self.captions = bool(inputs_by_title['CAPTIONS'].input.find('text[@name="Text.Text"]').text)

            self.audio_master_inputs = [i.input.attrib for i in inputs if
                                        'audiobusses' in i.input.attrib
                                        and 'M' in i.input.attrib['audiobusses']
                                        and i.input.attrib['muted'] == 'False'
                                        and float(i.input.attrib['volume']) > 0]
            self.audio_master = xml.find('audio/master').attrib

            self.recording = xml.find('recording').text.strip() == 'True'
            self.streaming = xml.find('streaming').attrib
        except KeyError:
            pass
