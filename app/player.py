import argparse
import bisect
from contextlib import contextmanager
import ctypes as win
from ctypes import wintypes
import json
import math
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from visuals import CHAPTERS, Film

ROOT = Path(__file__).resolve().parent
ENTER_SCREEN = '\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J'
LEAVE_SCREEN = '\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l'


@contextmanager
def terminal_screen():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('请在 Windows Terminal、PowerShell 或 CMD 中直接运行。')
    kernel = win.WinDLL('kernel32', use_last_error=True)
    kernel.GetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.LPDWORD)
    kernel.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WriteConsoleW.argtypes = (wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD,
                                     wintypes.LPDWORD, win.c_void_p)
    descriptor = os.open('CONOUT$', os.O_RDWR | os.O_BINARY)
    try:
        output = msvcrt.get_osfhandle(descriptor)
        original = wintypes.DWORD()
        processed_output = 0x0001
        virtual_terminal_processing = 0x0004
        if not kernel.GetConsoleMode(output, win.byref(original)):
            raise win.WinError(win.get_last_error())
        if not kernel.SetConsoleMode(output, original.value | processed_output | virtual_terminal_processing):
            raise RuntimeError('当前终端无法启用字符动画，请使用 Windows Terminal。')

        def write(text):
            for start in range(0, len(text), 8192):
                part = text[start:start + 8192]
                length = len(part.encode('utf-16-le')) // 2
                written = wintypes.DWORD()
                if not kernel.WriteConsoleW(output, part, length, win.byref(written), None):
                    raise win.WinError(win.get_last_error())

        try:
            write(ENTER_SCREEN)
            yield descriptor, write
        finally:
            try:
                write(LEAVE_SCREEN)
            finally:
                kernel.SetConsoleMode(output, original.value)
    finally:
        os.close(descriptor)


class Audio:
    def __init__(self, path):
        self.state = None
        self.last_update = time.monotonic()
        self.ready = threading.Event()
        self.process = subprocess.Popen(
            [str(ROOT / 'audio-clock.exe'), str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def __enter__(self):
        if self.ready.wait(timeout=8) and self.state is not None:
            return self
        try:
            if self.process.poll() is not None or self.ready.is_set():
                raise self.error()
            raise RuntimeError('Windows 音频引擎没有响应。')
        finally:
            self.close()

    def __exit__(self, *_):
        self.close()

    def read(self):
        try:
            for line in self.process.stdout:
                position, duration, playing, ended = line.split()
                self.state = float(position), float(duration), playing == '1', ended == '1'
                self.last_update = time.monotonic()
                self.ready.set()
        finally:
            self.ready.set()

    def error(self):
        try:
            self.process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return RuntimeError('Windows 音频时钟停止更新。')
        details = self.process.stderr.read().strip()
        return RuntimeError(details or 'Windows 音频引擎意外退出。')

    def command(self, command):
        try:
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise self.error() from error

    def close(self):
        try:
            if self.process.poll() is None:
                self.command('quit')
                self.process.wait(timeout=2)
        except (RuntimeError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait()
        finally:
            self.reader.join(timeout=1)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process.stderr.close()


def read_key_until(deadline):
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in ('\x00', '\xe0'):
                return {'K': 'Left', 'M': 'Right'}.get(msvcrt.getwch(), '')
            return key
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(remaining, 0.01))


def run(args, film):
    path = Path(args.audio).expanduser().resolve() if args.audio else ROOT / film.config['audio']
    if not path.is_file():
        raise RuntimeError(f'找不到音频：{path}')
    offset = args.offset if args.offset is not None else film.config.get('subtitle_offset', 0)
    ready = not (args.autoplay or args.paused)
    paused = not args.autoplay
    help_open = False
    volume = 0.30
    current = args.start
    last_size = None
    frames = 0
    max_render = 0
    samples = []
    try:
        with terminal_screen() as (descriptor, write), Audio(path) as audio:
            audio.command(f'volume {volume}')
            audio.command(f'seek {args.start}')
            if args.autoplay:
                audio.command('play')
            next_frame = time.monotonic()
            while True:
                begin = time.monotonic()
                if audio.process.poll() is not None or begin - audio.last_update > 2:
                    raise audio.error()
                current, duration, playing, ended = audio.state
                if ended:
                    paused = True
                columns, rows = os.get_terminal_size(descriptor)
                size = min(columns - 1, 240), min(rows, 85)
                if size != last_size:
                    write('\x1b[2J')
                    last_size = size
                canvas = film.render(current, *size, paused, offset, help_open, ready)
                write(canvas.ansi())

                frames += 1
                max_render = max(max_render, time.monotonic() - begin)
                if args.report and frames % 30 == 0:
                    samples.append(dict(audio_time=current, playing=playing, width=columns, height=rows, frames=frames))
                if args.stop_after is not None and (current >= args.stop_after or ended):
                    return
                next_frame = max(next_frame + 1 / args.fps, time.monotonic())
                while (key := read_key_until(next_frame)) is not None:
                    if key in ('q', 'Q', '\x1b', '\x03'):
                        return
                    if key in ('Left', 'Right'):
                        current += 5 if key == 'Right' else -5
                        current = max(0, min(duration - 0.05, current))
                        audio.command(f'seek {current}')
                    elif key in (' ', '\r', '\n'):
                        paused = not paused
                        ready = False
                        audio.command('pause' if paused else 'play')
                    elif key.lower() == 'r' or key in ('1', '2', '3', '4', '5'):
                        current = 0 if key.lower() == 'r' else CHAPTERS[int(key) - 1][0]
                        audio.command(f'seek {current}')
                        audio.command('play')
                        ready = paused = False
                    elif key in ('[', ']'):
                        offset = round(offset + (0.1 if key == '[' else -0.1), 2)
                    elif key in (',', '.'):
                        index = bisect.bisect_right(film.times, current + 0.03) - 1
                        index = max(0, min(len(film.times) - 1, index + (1 if key == '.' else -1)))
                        current = film.times[index]
                        audio.command(f'seek {current}')
                        ready = False
                    elif key.lower() == 'h':
                        help_open = not help_open
                    elif key in ('+', '=', '-'):
                        volume = max(0, min(1, volume + (-0.05 if key == '-' else 0.05)))
                        audio.command(f'volume {volume}')
    finally:
        if args.report:
            Path(args.report).write_text(json.dumps({
                'frames': frames, 'last_time': current,
                'max_frame_render_seconds': max_render, 'samples': samples,
            }, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='world.execute(me); / bilingual terminal MV for Windows')
    parser.add_argument('--audio')
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--autoplay', action='store_true')
    parser.add_argument('--paused', action='store_true')
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--offset', type=float)
    parser.add_argument('--snapshot', type=float)
    parser.add_argument('--width', type=int, default=120)
    parser.add_argument('--height', type=int, default=40)
    parser.add_argument('--plain', action='store_true')
    parser.add_argument('--report')
    parser.add_argument('--stop-after', type=float)
    args = parser.parse_args()
    if not 5 <= args.fps <= 60:
        parser.error('--fps must be between 5 and 60')
    if any(value is not None and not math.isfinite(value)
           for value in (args.start, args.offset, args.snapshot, args.stop_after)):
        parser.error('time values must be finite')
    if args.width < 1 or args.height < 1:
        parser.error('--width and --height must be positive')
    film = Film()
    if args.snapshot is not None:
        frame = film.render(max(0, args.snapshot), args.width, args.height, True)
        print(frame.plain() if args.plain else frame.ansi())
        return 0
    try:
        run(args, film)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as error:
        print(f'播放失败：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
