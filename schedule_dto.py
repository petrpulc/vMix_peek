from dataclasses import dataclass
from datetime import datetime

SKIP_KINDS = {'', 'Poster Session [In Person]', 'Break'}


@dataclass(frozen=True)
class Event:
    name: str
    kind: str
    start: datetime
    end: datetime
    note: str

    def is_current(self):
        return self.start <= datetime.now() < self.end


def _get(l, idx, default: str | None = ''):
    try:
        return l[idx]
    except IndexError:
        return default


def _parse_date(d):
    try:
        return datetime.strptime(d, '%b %d, %H:%M').replace(2024)
    except ValueError:
        return datetime(1970, 1, 1)


class ScheduleDTO:
    def __init__(self, schedule) -> None:
        events = []
        for row in schedule:
            if _get(row, 5) in SKIP_KINDS:
                continue

            events.append(
                Event(_get(row, 3), _get(row, 5), _parse_date(_get(row, 6)), _parse_date(_get(row, 7)), _get(row, 10)))

        self.events = sorted(events, key=lambda e: e.start)

    def get_current(self):
        return [e for e in self.events if e.is_current()]

    def get_previous(self):
        return _get([e for e in self.events if e.end < datetime.now()][-1:], 0, None)

    def get_next(self):
        return _get([e for e in self.events if e.start > datetime.now()][:1], 0, None)
