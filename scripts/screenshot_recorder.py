#!/usr/bin/env python3
"""
Screenshot-based recorder for Dusk tests.
Works on macOS, Linux, and Windows - no GUI interaction needed.

This uses Selenium's screenshot capability to capture frames,
then stitches them into a video with ffmpeg.

Requirements:
    pip install selenium websocket-client

Usage:
    # In your PHP test, call the Python recorder via HTTP or file signals
    # Or use the PHP trait that captures screenshots during test execution
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Try to import websocket for CDP
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class ScreenshotRecorder:
    """Records screenshots from Chrome via CDP and creates a video."""

    def __init__(self, cdp_url=None, output_dir=None, fps=10):
        self.cdp_url = cdp_url
        self.output_dir = output_dir or '/tmp/dusk-screenshots'
        self.fps = fps
        self.frames = []
        self.recording = False
        self.frame_count = 0
        self.ws = None

    def connect_cdp(self, debugger_url):
        """Connect to Chrome DevTools Protocol."""
        if not HAS_WEBSOCKET:
            raise ImportError("websocket-client required: pip install websocket-client")

        self.ws = websocket.create_connection(debugger_url)
        return True

    def take_screenshot_cdp(self):
        """Take screenshot via CDP."""
        if not self.ws:
            return None

        msg_id = int(time.time() * 1000)
        self.ws.send(json.dumps({
            'id': msg_id,
            'method': 'Page.captureScreenshot',
            'params': {'format': 'png'}
        }))

        response = json.loads(self.ws.recv())
        if 'result' in response and 'data' in response['result']:
            import base64
            return base64.b64decode(response['result']['data'])
        return None

    def save_frame(self, frame_data):
        """Save a frame to disk."""
        os.makedirs(self.output_dir, exist_ok=True)
        frame_path = os.path.join(self.output_dir, f'frame_{self.frame_count:06d}.png')
        with open(frame_path, 'wb') as f:
            f.write(frame_data)
        self.frame_count += 1
        return frame_path

    def start_recording(self, interval_ms=100):
        """Start capturing screenshots at regular intervals."""
        self.recording = True
        self.frame_count = 0

        # Clear previous frames
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

        def capture_loop():
            while self.recording:
                try:
                    frame = self.take_screenshot_cdp()
                    if frame:
                        self.save_frame(frame)
                except Exception as e:
                    print(f"Capture error: {e}")
                time.sleep(interval_ms / 1000)

        self.capture_thread = threading.Thread(target=capture_loop, daemon=True)
        self.capture_thread.start()

    def stop_recording(self, output_file):
        """Stop recording and create video."""
        self.recording = False
        time.sleep(0.5)  # Wait for last captures

        if self.ws:
            self.ws.close()

        return self.create_video(output_file)

    def create_video(self, output_file):
        """Create video from captured frames using ffmpeg."""
        if self.frame_count < 2:
            print("Not enough frames captured")
            return None

        # Ensure output directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(self.fps),
            '-i', os.path.join(self.output_dir, 'frame_%06d.png'),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'fast',
            output_file
        ]

        result = subprocess.run(cmd, capture_output=True)

        # Cleanup frames
        shutil.rmtree(self.output_dir, ignore_errors=True)

        if result.returncode == 0:
            print(f"Video created: {output_file}")
            return output_file
        else:
            print(f"ffmpeg error: {result.stderr.decode()}")
            return None


class RecorderHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for controlling the recorder."""

    recorder = None
    output_file = None

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else ''

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if path == '/start':
            # Start recording
            debugger_url = data.get('debugger_url')
            output = data.get('output', '/tmp/dusk-recording.mp4')
            fps = data.get('fps', 10)

            if not debugger_url:
                self.send_error(400, 'debugger_url required')
                return

            RecorderHTTPHandler.output_file = output
            RecorderHTTPHandler.recorder = ScreenshotRecorder(fps=fps)
            RecorderHTTPHandler.recorder.connect_cdp(debugger_url)
            RecorderHTTPHandler.recorder.start_recording(interval_ms=1000 // fps)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'recording'}).encode())

        elif path == '/frame':
            # Capture single frame (for manual capture mode)
            if RecorderHTTPHandler.recorder and RecorderHTTPHandler.recorder.ws:
                frame = RecorderHTTPHandler.recorder.take_screenshot_cdp()
                if frame:
                    RecorderHTTPHandler.recorder.save_frame(frame)

            self.send_response(200)
            self.end_headers()

        elif path == '/stop':
            # Stop recording and create video
            if RecorderHTTPHandler.recorder:
                output = RecorderHTTPHandler.recorder.stop_recording(
                    RecorderHTTPHandler.output_file
                )
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'stopped',
                    'output': output
                }).encode())
            else:
                self.send_error(400, 'No recording in progress')

        else:
            self.send_error(404, 'Not found')

    def log_message(self, format, *args):
        pass  # Suppress logging


def run_server(port=9876):
    """Run the HTTP control server."""
    server = HTTPServer(('127.0.0.1', port), RecorderHTTPHandler)
    print(f"Recorder server running on http://127.0.0.1:{port}")
    print("Endpoints:")
    print("  POST /start - Start recording (body: {debugger_url, output, fps})")
    print("  POST /frame - Capture single frame")
    print("  POST /stop  - Stop and create video")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Screenshot-based recorder')
    parser.add_argument('--server', action='store_true', help='Run HTTP server mode')
    parser.add_argument('--port', type=int, default=9876, help='Server port')

    args = parser.parse_args()

    if args.server:
        run_server(args.port)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
