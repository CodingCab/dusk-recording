#!/usr/bin/env python3
"""
Headless screen recorder for Dusk tests.
Uses Xvfb (virtual framebuffer) + ffmpeg for true headless recording.

Requirements:
    - Xvfb: apt-get install xvfb
    - ffmpeg: apt-get install ffmpeg
    - Python packages: pip install pyvirtualdisplay

Usage:
    # Start recording in background
    python headless_recorder.py start --output recording.mp4

    # Run your tests
    DISPLAY=:99 php artisan dusk

    # Stop recording
    python headless_recorder.py stop

For Docker, add to your Dockerfile:
    RUN apt-get update && apt-get install -y xvfb ffmpeg
"""

import subprocess
import sys
import os
import signal
import time
import argparse
from pathlib import Path

PID_FILE = '/tmp/dusk-recorder.pid'
DISPLAY_NUM = 99
SCREEN_SIZE = '1920x1080x24'


class HeadlessRecorder:
    def __init__(self, display=DISPLAY_NUM, size=SCREEN_SIZE):
        self.display = display
        self.size = size
        self.xvfb_proc = None
        self.ffmpeg_proc = None

    def start_xvfb(self):
        """Start Xvfb virtual display."""
        cmd = [
            'Xvfb',
            f':{self.display}',
            '-screen', '0', self.size,
            '-ac',  # Disable access control
        ]
        self.xvfb_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)  # Wait for Xvfb to start
        print(f"Started Xvfb on display :{self.display}")
        return self.xvfb_proc.pid

    def start_recording(self, output_file):
        """Start ffmpeg recording of the virtual display."""
        # Ensure output directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-f', 'x11grab',  # X11 screen capture
            '-video_size', self.size.split('x')[0] + 'x' + self.size.split('x')[1],
            '-framerate', '15',
            '-i', f':{self.display}',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            output_file
        ]

        self.ffmpeg_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"Started recording to {output_file}")
        return self.ffmpeg_proc.pid

    def stop(self):
        """Stop recording and Xvfb."""
        if self.ffmpeg_proc:
            # Send 'q' to ffmpeg to stop gracefully
            try:
                self.ffmpeg_proc.stdin.write(b'q')
                self.ffmpeg_proc.stdin.flush()
                self.ffmpeg_proc.wait(timeout=5)
            except:
                self.ffmpeg_proc.terminate()
            print("Stopped recording")

        if self.xvfb_proc:
            self.xvfb_proc.terminate()
            print("Stopped Xvfb")

    def save_pids(self, xvfb_pid, ffmpeg_pid, output_file):
        """Save PIDs to file for later stopping."""
        with open(PID_FILE, 'w') as f:
            f.write(f"{xvfb_pid}\n{ffmpeg_pid}\n{output_file}\n")

    @staticmethod
    def load_pids():
        """Load PIDs from file."""
        if not os.path.exists(PID_FILE):
            return None, None, None
        with open(PID_FILE, 'r') as f:
            lines = f.readlines()
            if len(lines) >= 3:
                return int(lines[0].strip()), int(lines[1].strip()), lines[2].strip()
        return None, None, None

    @staticmethod
    def cleanup_pid_file():
        """Remove PID file."""
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


def start_recording(output_file, display=DISPLAY_NUM, size=SCREEN_SIZE):
    """Start headless recording."""
    recorder = HeadlessRecorder(display, size)

    xvfb_pid = recorder.start_xvfb()
    ffmpeg_pid = recorder.start_recording(output_file)

    recorder.save_pids(xvfb_pid, ffmpeg_pid, output_file)

    print(f"\nRecording started!")
    print(f"Run your tests with: DISPLAY=:{display} php artisan dusk")
    print(f"Stop recording with: python {sys.argv[0]} stop")

    return xvfb_pid, ffmpeg_pid


def stop_recording():
    """Stop headless recording."""
    xvfb_pid, ffmpeg_pid, output_file = HeadlessRecorder.load_pids()

    if not xvfb_pid:
        print("No recording in progress")
        return

    # Stop ffmpeg first (gracefully)
    try:
        os.kill(ffmpeg_pid, signal.SIGTERM)
        time.sleep(2)
    except ProcessLookupError:
        pass

    # Stop Xvfb
    try:
        os.kill(xvfb_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    HeadlessRecorder.cleanup_pid_file()

    print(f"Recording stopped. Output: {output_file}")


def run_with_recording(command, output_file, display=DISPLAY_NUM):
    """Run a command with recording enabled."""
    recorder = HeadlessRecorder(display)

    recorder.start_xvfb()
    recorder.start_recording(output_file)

    # Set environment for the command
    env = os.environ.copy()
    env['DISPLAY'] = f':{display}'

    try:
        # Run the command
        result = subprocess.run(command, shell=True, env=env)
        return result.returncode
    finally:
        recorder.stop()


def main():
    parser = argparse.ArgumentParser(description='Headless screen recorder for Dusk tests')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start recording')
    start_parser.add_argument('--output', '-o', default='recording.mp4', help='Output file')
    start_parser.add_argument('--display', '-d', type=int, default=DISPLAY_NUM, help='Display number')
    start_parser.add_argument('--size', '-s', default=SCREEN_SIZE, help='Screen size (WxHxD)')

    # Stop command
    subparsers.add_parser('stop', help='Stop recording')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run command with recording')
    run_parser.add_argument('--output', '-o', default='recording.mp4', help='Output file')
    run_parser.add_argument('--display', '-d', type=int, default=DISPLAY_NUM, help='Display number')
    run_parser.add_argument('cmd', nargs=argparse.REMAINDER, help='Command to run')

    args = parser.parse_args()

    if args.command == 'start':
        start_recording(args.output, args.display, args.size)
    elif args.command == 'stop':
        stop_recording()
    elif args.command == 'run':
        cmd = ' '.join(args.cmd) if args.cmd else 'php artisan dusk'
        sys.exit(run_with_recording(cmd, args.output, args.display))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
