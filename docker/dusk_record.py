#!/usr/bin/env python3
"""
Dusk Test Recorder

Spins up a Docker container with virtual display, runs a Dusk test with
screen recording, and saves the video.

Usage:
    python dusk_record.py <test-file> [output-name] [--build]

Examples:
    python dusk_record.py tests/Browser/LoginTest.php
    python dusk_record.py tests/Browser/DashboardTest.php dashboard-demo
    python dusk_record.py tests/Browser/CheckoutTest.php --build

Requirements:
    - Docker
    - Python 3.6+
"""

import argparse
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime


# Configuration
IMAGE_NAME = "dusk-recorder"
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "./storage/recordings")


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.NC = ''


def print_color(color, message):
    print(f"{color}{message}{Colors.NC}")


def print_header(title):
    print_color(Colors.GREEN, "=" * 50)
    print_color(Colors.GREEN, title)
    print_color(Colors.GREEN, "=" * 50)


def check_docker():
    """Check if Docker is available."""
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def image_exists(image_name):
    """Check if Docker image exists."""
    result = subprocess.run(
        ["docker", "image", "inspect", image_name],
        capture_output=True
    )
    return result.returncode == 0


def build_image(dockerfile_dir):
    """Build the Docker image."""
    print_color(Colors.YELLOW, "Building Docker image...")

    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_NAME, dockerfile_dir],
        capture_output=False
    )

    if result.returncode != 0:
        print_color(Colors.RED, "Failed to build Docker image")
        sys.exit(1)

    print_color(Colors.GREEN, "Docker image built successfully")


def get_file_info(filepath):
    """Get file size and duration (if ffprobe available)."""
    info = {}

    if os.path.exists(filepath):
        size_bytes = os.path.getsize(filepath)
        if size_bytes >= 1024 * 1024:
            info['size'] = f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            info['size'] = f"{size_bytes / 1024:.1f}KB"

        # Try to get duration with ffprobe
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                info['duration'] = f"{int(duration)}s"
        except:
            pass

    return info


def run_recording(test_file, output_name, recordings_dir):
    """Run the Docker container and record the test."""

    container_name = f"dusk-recorder-{os.getpid()}"
    project_dir = os.getcwd()

    # Prepare environment variables for database connection
    env_vars = {
        "APP_ENV": "testing",
        "APP_DEBUG": "true",
        "DB_CONNECTION": os.environ.get("DB_CONNECTION", "mysql"),
        "DB_HOST": os.environ.get("DB_HOST", "host.docker.internal"),
        "DB_PORT": os.environ.get("DB_PORT", "3306"),
        "DB_DATABASE": os.environ.get("DB_DATABASE", "testing"),
        "DB_USERNAME": os.environ.get("DB_USERNAME", "root"),
        "DB_PASSWORD": os.environ.get("DB_PASSWORD", ""),
    }

    # Build docker run command
    cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--shm-size=2g",
        "-v", f"{project_dir}:/app",
        "-v", f"{os.path.abspath(recordings_dir)}:/recordings",
        "--tmpfs", "/app/.phpunit.cache:rw,size=64m",
    ]

    # Add environment variables
    for key, value in env_vars.items():
        cmd.extend(["-e", f"{key}={value}"])

    # Add image and command
    cmd.extend([
        IMAGE_NAME,
        test_file, output_name
    ])

    print_color(Colors.YELLOW, "Starting recording container...")
    print()

    # Run the container
    result = subprocess.run(cmd)

    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Record Dusk tests in a Docker container with virtual display",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s tests/Browser/LoginTest.php
  %(prog)s tests/Browser/DashboardTest.php dashboard-demo
  %(prog)s tests/Browser/LoginTest.php --build

Environment variables:
  RECORDINGS_DIR  Where to save recordings (default: ./storage/recordings)
  DB_HOST         Database host (default: host.docker.internal)
  DB_DATABASE     Database name (default: testing)
  DB_USERNAME     Database user (default: root)
  DB_PASSWORD     Database password
"""
    )

    parser.add_argument(
        "test_file",
        help="Path to the Dusk test file"
    )
    parser.add_argument(
        "output_name",
        nargs="?",
        help="Name for the recording (optional, auto-generated if not provided)"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild the Docker image before running"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    # Check Docker
    if not check_docker():
        print_color(Colors.RED, "Error: Docker is not installed or not running")
        sys.exit(1)

    # Check test file exists
    if not os.path.exists(args.test_file):
        print_color(Colors.RED, f"Error: Test file not found: {args.test_file}")
        sys.exit(1)

    # Create recordings directory
    recordings_dir = RECORDINGS_DIR
    os.makedirs(recordings_dir, exist_ok=True)

    # Generate output name if not provided
    output_name = args.output_name
    if not output_name:
        base_name = Path(args.test_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_{timestamp}"

    # Get script directory for Dockerfile
    script_dir = Path(__file__).parent

    # Build image if needed
    if args.build or not image_exists(IMAGE_NAME):
        build_image(script_dir)

    # Print info
    print()
    print_header("Dusk Test Recorder")
    print(f"Test:       {args.test_file}")
    print(f"Output:     {recordings_dir}/{output_name}.mp4")
    print(f"Image:      {IMAGE_NAME}")
    print()

    # Run the recording
    exit_code = run_recording(args.test_file, output_name, recordings_dir)

    # Print results
    print()
    recording_file = os.path.join(recordings_dir, f"{output_name}.mp4")

    if exit_code == 0:
        if os.path.exists(recording_file):
            print_header("Recording Complete!")
            print(f"File: {recording_file}")

            file_info = get_file_info(recording_file)
            if 'size' in file_info:
                print(f"Size: {file_info['size']}")
            if 'duration' in file_info:
                print(f"Duration: {file_info['duration']}")
        else:
            print_color(Colors.YELLOW, "Warning: Recording file not found")
    else:
        print_color(Colors.RED, f"Test failed with exit code: {exit_code}")
        if os.path.exists(recording_file):
            print(f"Recording (partial): {recording_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
