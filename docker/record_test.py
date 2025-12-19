#!/usr/bin/env python3
"""
Record a Dusk test inside the Docker container.

This script runs inside the Docker container and:
1. Starts screen recording with ffmpeg
2. Runs the specified Dusk test
3. Stops recording and saves the video

Usage:
    python record_test.py <test-file> [output-name]
"""

import argparse
import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime


class ScreenRecorder:
    """Manages ffmpeg screen recording."""

    def __init__(self, output_file, display=":99", resolution="1920x1080", fps=15):
        self.output_file = output_file
        self.display = display
        self.resolution = resolution
        self.fps = fps
        self.process = None
        self.temp_file = f"/tmp/recording_{os.getpid()}.webm"

    def start(self):
        """Start screen recording."""
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-video_size", self.resolution,
            "-framerate", str(self.fps),
            "-i", self.display,
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
            self.temp_file
        ]

        # Start ffmpeg in background, suppressing output
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE
        )

        # Wait a moment for ffmpeg to start
        time.sleep(2)

        # Check if process is still running
        if self.process.poll() is not None:
            raise RuntimeError("Failed to start screen recording")

        return self.process.pid

    def stop(self):
        """Stop recording and finalize the video."""
        if self.process is None:
            return None

        try:
            # Send SIGINT to stop ffmpeg gracefully
            self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        except Exception as e:
            print(f"Warning: Error stopping ffmpeg: {e}")

        # Move temp file to final location
        if os.path.exists(self.temp_file):
            import shutil
            Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self.temp_file, self.output_file)
            return self.output_file

        return None

    def get_video_info(self):
        """Get video file information."""
        if not os.path.exists(self.output_file):
            return None

        info = {
            'file': self.output_file,
            'size': os.path.getsize(self.output_file)
        }

        # Try to get duration with ffprobe
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", self.output_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['duration'] = float(result.stdout.strip())
        except:
            pass

        return info


def wait_for_display(display=":99", timeout=10):
    """Wait for the virtual display to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Try to connect to the display
            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def run_dusk_test(test_file):
    """Run a Dusk test and return the exit code."""
    cmd = ["php", "artisan", "dusk", test_file]

    result = subprocess.run(cmd)
    return result.returncode


def format_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes}B"


def main():
    parser = argparse.ArgumentParser(
        description="Record a Dusk test execution"
    )
    parser.add_argument(
        "test_file",
        help="Path to the Dusk test file"
    )
    parser.add_argument(
        "output_name",
        nargs="?",
        help="Name for the recording (without extension)"
    )
    parser.add_argument(
        "--display",
        default=":99",
        help="X display to record (default: :99)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=15,
        help="Frames per second (default: 15)"
    )
    parser.add_argument(
        "--resolution",
        default="1920x1080",
        help="Recording resolution (default: 1920x1080)"
    )

    args = parser.parse_args()

    # Generate output name if not provided
    output_name = args.output_name
    if not output_name:
        base_name = Path(args.test_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_{timestamp}"

    # Ensure .webm extension
    if not output_name.endswith('.webm'):
        output_name = output_name.replace('.mp4', '')
    output_file = f"/recordings/{output_name}.webm"

    # Print header
    print("=" * 50)
    print("Dusk Test Recorder")
    print("=" * 50)
    print(f"Test file:   {args.test_file}")
    print(f"Output:      {output_file}")
    print(f"Display:     {args.display}")
    print(f"Resolution:  {args.resolution}")
    print(f"FPS:         {args.fps}")
    print("=" * 50)
    print()

    # Wait for display
    print("Waiting for virtual display...")
    if not wait_for_display(args.display):
        print("Warning: Could not verify display is ready, continuing anyway...")

    # Start recording
    print("Starting screen recording...")
    recorder = ScreenRecorder(
        output_file,
        display=args.display,
        resolution=args.resolution,
        fps=args.fps
    )

    try:
        pid = recorder.start()
        print(f"Recording started (PID: {pid})")
    except Exception as e:
        print(f"ERROR: Failed to start recording: {e}")
        sys.exit(1)

    print()
    print("=" * 50)
    print(f"Running test: {args.test_file}")
    print("=" * 50)
    print()

    # Run the test
    test_exit_code = run_dusk_test(args.test_file)

    print()
    print("=" * 50)
    print(f"Test completed with exit code: {test_exit_code}")
    print("=" * 50)

    # Stop recording
    print()
    print("Stopping recording...")
    time.sleep(1)  # Give a moment for any final frames

    final_file = recorder.stop()

    if final_file and os.path.exists(final_file):
        info = recorder.get_video_info()
        print(f"Recording saved: {final_file}")
        if info:
            print(f"Size: {format_size(info.get('size', 0))}")
            if 'duration' in info:
                print(f"Duration: {int(info['duration'])}s")
    else:
        print("WARNING: Recording file not created")

    sys.exit(test_exit_code)


if __name__ == "__main__":
    main()
