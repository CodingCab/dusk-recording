#!/usr/bin/env python3
"""
Docker entrypoint for Dusk Recording container.

Starts the virtual display and ChromeDriver, then runs the test recording.

Usage:
    python entrypoint.py <test-file> [output-name] [options]
"""

import argparse
import os
import sys
import subprocess
import signal
import time
import atexit


class ServiceManager:
    """Manages background services (Xvfb, ChromeDriver)."""

    def __init__(self):
        self.processes = []

    def start_xvfb(self, display=":99", resolution="1920x1080x24"):
        """Start Xvfb virtual display."""
        cmd = [
            "Xvfb", display,
            "-screen", "0", resolution,
            "-ac",  # Disable access control
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.processes.append(("Xvfb", proc))

        # Wait for display to be ready
        time.sleep(2)

        # Verify display is working
        try:
            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"Virtual display started on {display}")
                return True
        except:
            pass

        print(f"Warning: Could not verify display {display}")
        return False

    def start_chromedriver(self, port=9515):
        """Start ChromeDriver."""
        cmd = [
            "chromedriver",
            f"--port={port}",
            "--whitelisted-ips=",
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.processes.append(("ChromeDriver", proc))

        # Wait for ChromeDriver to be ready
        time.sleep(2)

        # Verify ChromeDriver is running
        if proc.poll() is None:
            print(f"ChromeDriver started on port {port}")
            return True

        print("Warning: ChromeDriver may not have started correctly")
        return False

    def stop_all(self):
        """Stop all managed processes."""
        for name, proc in reversed(self.processes):
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    proc.kill()
                print(f"Stopped {name}")

    def wait_for_services(self, timeout=30):
        """Wait for all services to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            all_running = all(proc.poll() is None for _, proc in self.processes)
            if all_running:
                return True
            time.sleep(0.5)
        return False


def run_recording(test_file, output_name, **kwargs):
    """Run the test recording script."""
    cmd = ["python3", "/usr/local/bin/record_test.py", test_file]

    if output_name:
        cmd.append(output_name)

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Dusk Test Recording Container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python entrypoint.py tests/Browser/LoginTest.php
  python entrypoint.py tests/Browser/LoginTest.php login-demo
  python entrypoint.py tests/Browser/LoginTest.php --fps 30

The container will:
  1. Start a virtual display (Xvfb)
  2. Start ChromeDriver
  3. Run the specified test with screen recording
  4. Save the recording to /recordings/
"""
    )

    parser.add_argument(
        "test_file",
        nargs="?",
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
        help="X display number (default: :99)"
    )
    parser.add_argument(
        "--resolution",
        default="1920x1080",
        help="Recording resolution (default: 1920x1080)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=15,
        help="Frames per second (default: 15)"
    )
    parser.add_argument(
        "--chromedriver-port",
        type=int,
        default=9515,
        help="ChromeDriver port (default: 9515)"
    )

    args = parser.parse_args()

    # Show help if no test file provided
    if not args.test_file:
        parser.print_help()
        print("\nNo test file specified.")
        sys.exit(0)

    # Initialize service manager
    services = ServiceManager()

    # Register cleanup handler
    def cleanup():
        services.stop_all()

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    print("=" * 50)
    print("Dusk Recording Container")
    print("=" * 50)
    print()

    # Start services
    print("Starting services...")

    if not services.start_xvfb(args.display, f"{args.resolution}x24"):
        print("ERROR: Failed to start virtual display")
        sys.exit(1)

    if not services.start_chromedriver(args.chromedriver_port):
        print("ERROR: Failed to start ChromeDriver")
        sys.exit(1)

    print()
    print("Services ready. Starting test recording...")
    print()

    # Run the recording
    exit_code = run_recording(
        args.test_file,
        args.output_name,
        display=args.display,
        resolution=args.resolution,
        fps=args.fps
    )

    # Cleanup is handled by atexit
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
