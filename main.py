import json
import webbrowser
from collections import deque
from xml.etree.ElementTree import fromstring

import httpx
from googleapiclient.discovery import build
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Label, Sparkline, Markdown

import credentials
from schedule_dto import ScheduleDTO
from vmix_dto import VMixDTO

CAMERA_INPUTS = {'CAM1', 'WIDESHOT', 'STARTING SOON [D1]', 'ZOOM CAM [D4]', 'FINISH [F]'}
SLIDE_INPUTS = {'SLIDES VENUE [C]', 'VIDEO IS PLAYING [V]', 'LOGO [X]', 'ZOOM SLIDES [C]'}
VENUE_INPUTS = SLIDE_INPUTS.union(('CAPTIONS',))

STREAMING_CAMERA = {'CAM1', 'WIDESHOT', 'ZOOM CAM [D4]'}
STREAMING_SLIDES = {'SLIDES VENUE [C]', 'VIDEO IS PLAYING [V]', 'ZOOM SLIDES [C]'}
STREAMING_AUDIO = {'MAIN AUDIO - VENUE [F8]', 'ZOOM AUDIO (VB-Audio Cable A)'}
BREAK_CAMERA = {'STARTING SOON [D1]', 'FINISH [F]'}
BREAK_SLIDES = {'LOGO [X]'}

DEBUG = False
LOCAL = False


class Session(Static):
    def __init__(self, url, sheet, room, streamer):
        self.url = url
        self.sheet = sheet
        self.room = room
        self.streamer = streamer

        self.google_sheets = None

        self.vmix = None
        self.audio_monitor_l = deque(maxlen=10)
        self.audio_monitor_r = deque(maxlen=10)
        self.caption_monitor = deque(maxlen=5)

        self.schedule = None
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"{self.sheet}  {self.room}  {self.streamer}  [@click=app.browser('{self.url}')]{self.url}[/ ]")
        yield Horizontal(
            Label(id="cam"),
            Label(id="slides"),
            Label(id="venue"),
            Label(id="captions"),
            Label(id="recording"),
            Label(id="streaming"),
            Markdown(id="audio"),
            Vertical(
                Sparkline(self.audio_monitor_l, id="audio_monitor_l"),
                Sparkline(self.audio_monitor_r, id="audio_monitor_r"),
                id="meters")
        )
        yield Markdown(id="schedule")

    def on_mount(self) -> None:
        self.set_interval(5, self.fetch_vmix)
        self.set_timer(1 / 30, self.fetch_vmix)
        self.set_interval(300, self.fetch_google_sheets)
        self.set_timer(1 / 30, self.fetch_google_sheets)

    def fetch_google_sheets(self) -> None:
        if LOCAL:
            data = json.load(open('schedule.json'))
        else:
            if self.google_sheets is None:
                self.google_sheets = build("sheets", "v4", developerKey=credentials.google_key).spreadsheets().values()
            data = \
                self.google_sheets.get(spreadsheetId=credentials.google_sheet_id,
                                       range=f"{self.sheet}!A9:K").execute()[
                    'values']

        self.schedule = ScheduleDTO(data)
        self.update_schedule()

    def update_schedule(self):
        table = "|Title|Start|End|Note|\n"
        table += "| - | - | - | - |\n"
        # if self.schedule.previous:
        #    table += f"|{self.schedule.previous.name}|{self.schedule.previous.start}|{self.schedule.previous.end}|{self.schedule.previous.note}|\n"

        if self.schedule.get_current():
            for e in self.schedule.get_current():
                table += f"|**{e.name}**|{e.start}|{e.end}|{e.note}|\n"
        elif self.schedule.get_next():
            table += f"|*{self.schedule.get_next().name}*|{self.schedule.get_next().start}|{self.schedule.get_next().end}|{self.schedule.get_next().note}|\n"

        self.query_one('#schedule', Markdown).update(table)

    async def fetch_vmix(self) -> None:
        if LOCAL:
            xml = fromstring(open('2.xml').read())
        else:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(self.url)
                    xml = fromstring(response.content)
                except Exception:
                    return

        self.vmix = VMixDTO(xml)
        self.update_vmix()
        if self.schedule:
            self.update_schedule()

    def update_vmix(self):
        if self.vmix is None:
            return

        self.audio_monitor_l.append(float(self.vmix.audio_master.get('meterF1', 0)))
        self.audio_monitor_r.append(float(self.vmix.audio_master.get('meterF2', 0)))
        self.query_one('#audio_monitor_l', Sparkline).refresh()
        self.query_one('#audio_monitor_r', Sparkline).refresh()

        self.caption_monitor.append(self.vmix.captions)
        self.query_one('#captions', Label).update('💬' if any(self.caption_monitor) else '🤐')

        self.query_one('#recording', Label).update('🔴' if self.vmix.recording else '⏹️')
        if self.vmix.streaming.get('channel1', '') == 'True' and self.vmix.streaming.get('channel2', '') == 'True':
            self.query_one('#streaming', Label).update('🌍')
        elif self.vmix.streaming.get('channel1', '') == 'True' or self.vmix.streaming.get('channel2', '') == 'True':
            self.query_one('#streaming', Label).update('⚠️')
        else:
            self.query_one('#streaming', Label).update('😭')

        stream_cam = self.vmix.stream_cam
        stream_slides = self.vmix.stream_slides
        venue = self.vmix.venue

        if not DEBUG:
            stream_cam = stream_cam.intersection(CAMERA_INPUTS)
            stream_slides = stream_slides.intersection(SLIDE_INPUTS)
            venue = venue.intersection(VENUE_INPUTS)

        self.query_one('#cam', Label).update(', '.join(sorted(stream_cam)))
        self.query_one('#slides', Label).update(', '.join(sorted(stream_slides)))
        self.query_one('#venue', Label).update(', '.join(sorted(venue)))

        audio = ', '.join(f'**{i["title"]}**' if float(i['meterF1']) > 0.1 else i["title"] for i in
                          sorted(self.vmix.audio_master_inputs, key=lambda x: float(x['meterF1']), reverse=True))
        self.query_one('#audio', Markdown).update(audio)

        # Checks
        if self.schedule:
            if self.schedule.get_current():
                if stream_cam.intersection(STREAMING_CAMERA):
                    self.query_one("#cam").remove_class("error")
                else:
                    self.query_one("#cam").add_class("error")

                if stream_slides.intersection(STREAMING_SLIDES):
                    self.query_one("#slides").remove_class("error")
                else:
                    self.query_one("#slides").add_class("error")

                if set(i['title'] for i in self.vmix.audio_master_inputs).intersection(STREAMING_AUDIO):
                    self.query_one("#audio").remove_class("error")
                else:
                    self.query_one("#audio").add_class("error")

                if self.vmix.recording:
                    self.query_one("#recording").remove_class("error_icon")
                    self.query_one("#recording").remove_class("warn_icon")
                else:
                    self.query_one("#recording").add_class("error_icon")
                    self.query_one("#recording").remove_class("warn_icon")

                if self.vmix.streaming.get('channel1', '') == 'True' and self.vmix.streaming.get('channel2',
                                                                                                 '') == 'True':
                    self.query_one("#streaming").remove_class("error_icon")
                else:
                    self.query_one("#streaming").add_class("error_icon")


            else:
                if stream_cam.intersection(BREAK_CAMERA):
                    self.query_one("#cam").remove_class("error")
                else:
                    self.query_one("#cam").add_class("error")

                if stream_slides.intersection(BREAK_SLIDES):
                    self.query_one("#slides").remove_class("error")
                else:
                    self.query_one("#slides").add_class("error")

                self.query_one("#audio").remove_class("error")

                if self.vmix.recording:
                    self.query_one("#recording").remove_class("error_icon")
                    self.query_one("#recording").add_class("warn_icon")
                else:
                    self.query_one("#recording").remove_class("error_icon")
                    self.query_one("#recording").remove_class("warn_icon")
                self.query_one("#streaming").remove_class("error_icon")


class VMixPeekApp(App):
    CSS_PATH = "textual.css"

    @staticmethod
    def action_browser(url):
        webbrowser.get('chrome').open(url)

    def compose(self) -> ComposeResult:
        streams = json.load(open('streams.json'))
        for streamer, rooms in streams.items():
            yield Horizontal(*[Session(r['vmix'], r['sheet'], r['room'], streamer) for r in rooms])


if __name__ == "__main__":
    app = VMixPeekApp()
    app.run()
