"""Build the portable Windows terminal release using a local MP3."""

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
EXCLUDED = {'site-packages', 'tkinter', 'idlelib', 'turtledemo', 'test', 'tests', 'ensurepip', '__pycache__'}
ARCHIVE_NAME = 'world-execute-mv-windows-terminal.zip'


def bundle_python(runtime):
    python = Path(sys.base_prefix)
    for file in ('python.exe', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copyfile(python / file, runtime / file)
    dlls = runtime / 'DLLs'
    dlls.mkdir()
    for file in ('_ctypes.pyd', 'libffi-8.dll', 'unicodedata.pyd'):
        shutil.copyfile(python / 'DLLs' / file, dlls / file)
    (runtime / 'python312._pth').write_text('python312.zip\nDLLs\n../app\n', encoding='ascii')

    library = python / 'Lib'
    with ZipFile(runtime / 'python312.zip', 'w', ZIP_DEFLATED) as archive:
        for folder, subdirs, filenames in os.walk(library):
            subdirs[:] = [name for name in subdirs if name not in EXCLUDED]
            for name in filenames:
                if name.endswith('.py'):
                    file = Path(folder) / name
                    archive.write(file, file.relative_to(library))


def build(song):
    framework = Path(os.environ['WINDIR']) / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319'
    wpf = framework / 'WPF'
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='world-execute-', dir=dist) as temp:
        stage = Path(temp)
        app = stage / 'app'
        media = app / 'media'
        media.mkdir(parents=True)
        for name in ('player.py', 'visuals.py', 'scenes.py', 'config.json', 'lyrics.json', 'spectrum.json'):
            shutil.copyfile(ROOT / 'app' / name, app / name)
        shutil.copyfile(song, media / 'song.mp3')
        for name in ('play.cmd', '使用说明.txt'):
            shutil.copyfile(ROOT / name, stage / name)

        subprocess.run([
            str(framework / 'csc.exe'), '/nologo', '/optimize+', '/target:exe',
            f'/reference:{wpf / "WindowsBase.dll"}', f'/reference:{wpf / "PresentationCore.dll"}',
            f'/out:{app / "audio-clock.exe"}', str(ROOT / 'AudioClock.cs'),
        ], check=True)
        runtime = stage / 'runtime'
        runtime.mkdir()
        bundle_python(runtime)

        package = stage / ARCHIVE_NAME
        with ZipFile(package, 'w', ZIP_DEFLATED) as archive:
            for file in sorted(stage.rglob('*')):
                if file.is_file() and file != package:
                    archive.write(file, file.relative_to(stage))
        with ZipFile(package) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('The generated ZIP failed validation.')
        package.replace(dist / ARCHIVE_NAME)
    return dist / ARCHIVE_NAME


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('song', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32' or struct.calcsize('P') != 8 or sys.version_info[:2] != (3, 12):
        parser.error('The build requires a complete 64-bit CPython 3.12 installation on Windows.')
    if not args.song.is_file():
        parser.error('The MP3 file does not exist.')
    print(build(args.song.resolve()))
