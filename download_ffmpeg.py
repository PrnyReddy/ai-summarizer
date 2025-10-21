#!/usr/bin/env python3
"""
Download and setup ffmpeg for Windows
"""

import urllib.request
import zipfile
import os
import shutil

def download_ffmpeg():
    """Download ffmpeg binary for Windows"""
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg.zip"

    print("Downloading ffmpeg...")
    urllib.request.urlretrieve(ffmpeg_url, zip_path)

    print("Extracting ffmpeg...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall('ffmpeg_temp')

    # Find ffmpeg.exe
    for root, dirs, files in os.walk('ffmpeg_temp'):
        if 'ffmpeg.exe' in files:
            ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
            shutil.copy2(ffmpeg_path, 'ffmpeg.exe')
            break

    # Cleanup
    shutil.rmtree('ffmpeg_temp')
    os.remove(zip_path)

    print("FFmpeg installed successfully!")

if __name__ == "__main__":
    download_ffmpeg()