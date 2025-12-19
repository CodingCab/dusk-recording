#!/usr/bin/env python3
"""
Auto-approve Chrome screen share dialog for Dusk recording.
Run this script before starting your Dusk tests.

Requirements:
    pip install pyautogui pillow

Usage:
    python auto_approve_screen_share.py &
    php artisan dusk
"""

import pyautogui
import time
import sys
import os

# Disable pyautogui fail-safe (moving mouse to corner won't abort)
pyautogui.FAILSAFE = False

# Screen share dialog detection settings
POLL_INTERVAL = 0.5  # seconds between checks
TIMEOUT = 300  # max seconds to run (5 minutes)

# Button text/images to look for (macOS Chrome)
SHARE_BUTTON_IMAGES = [
    'share_button.png',  # You can add screenshot of share button
]

# Text patterns for the share dialog
SHARE_DIALOG_TITLES = [
    'Choose what to share',
    'Share your screen',
    'Screen share',
]


def find_and_click_share_button():
    """Try to find and click the Share button in Chrome's screen share dialog."""

    # Method 1: Try to find by image (if screenshot provided)
    for img in SHARE_BUTTON_IMAGES:
        if os.path.exists(img):
            try:
                location = pyautogui.locateOnScreen(img, confidence=0.8)
                if location:
                    center = pyautogui.center(location)
                    pyautogui.click(center)
                    print(f"Clicked share button at {center}")
                    return True
            except Exception as e:
                pass

    # Method 2: Look for the dialog and click specific coordinates
    # Chrome's share dialog typically has "Entire screen" tab and "Share" button
    try:
        # On macOS, the share dialog is usually centered
        # We can try to click on common locations

        # First, try to find any window with share-related title
        import subprocess

        # Use AppleScript to find Chrome share dialog (macOS only)
        script = '''
        tell application "System Events"
            tell process "Google Chrome"
                set allWindows to every window
                repeat with w in allWindows
                    set winName to name of w
                    if winName contains "share" or winName contains "Share" or winName contains "screen" then
                        -- Click on the Share button (usually bottom right)
                        set winPos to position of w
                        set winSize to size of w
                        return (item 1 of winPos + item 1 of winSize - 100) & "," & (item 2 of winPos + item 2 of winSize - 50)
                    end if
                end repeat
            end tell
        end tell
        return ""
        '''

        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.stdout.strip():
            coords = result.stdout.strip().split(',')
            if len(coords) == 2:
                x, y = int(coords[0]), int(coords[1])
                pyautogui.click(x, y)
                print(f"Clicked share button at ({x}, {y})")
                return True

    except Exception as e:
        print(f"AppleScript method failed: {e}")

    return False


def click_entire_screen_option():
    """Click on 'Entire screen' option in the share dialog."""
    try:
        # Use AppleScript to interact with the dialog
        script = '''
        tell application "System Events"
            tell process "Google Chrome"
                -- Try to click on "Entire screen" or similar option
                set allWindows to every window
                repeat with w in allWindows
                    try
                        -- Look for radio buttons or tabs
                        set allButtons to every radio button of w
                        repeat with b in allButtons
                            if name of b contains "Entire" or name of b contains "Screen" then
                                click b
                                return "clicked"
                            end if
                        end repeat
                    end try
                end repeat
            end tell
        end tell
        return ""
        '''
        subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    except:
        pass


def monitor_and_approve():
    """Main loop to monitor for screen share dialogs and auto-approve them."""
    print("Screen share auto-approver started...")
    print(f"Monitoring for {TIMEOUT} seconds...")
    print("Press Ctrl+C to stop")

    start_time = time.time()
    approvals = 0

    while time.time() - start_time < TIMEOUT:
        try:
            # Check if Chrome share dialog is visible
            # First select entire screen, then click share
            click_entire_screen_option()
            time.sleep(0.2)

            if find_and_click_share_button():
                approvals += 1
                print(f"Approved screen share #{approvals}")
                time.sleep(2)  # Wait a bit after approval

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

    print(f"Done. Approved {approvals} screen share requests.")


def simple_keyboard_approve():
    """
    Simpler approach: Just press Tab + Enter to approve the default selection.
    Chrome's share dialog usually has "Entire screen" selected by default.
    """
    print("Simple keyboard auto-approver started...")
    print("This will press Tab+Enter when share dialog appears")
    print("Press Ctrl+C to stop")

    start_time = time.time()

    while time.time() - start_time < TIMEOUT:
        try:
            # Check for the share dialog by looking for Chrome to be focused
            # and then try Tab + Enter

            # This is a simple approach - just periodically try the keyboard shortcut
            # The share dialog, when focused, can be approved with keyboard

            time.sleep(POLL_INTERVAL)

            # Try to detect if dialog is open using AppleScript
            import subprocess
            script = '''
            tell application "System Events"
                tell process "Google Chrome"
                    set frontWindow to front window
                    if name of frontWindow contains "share" or name of frontWindow contains "Choose" then
                        return "dialog"
                    end if
                end tell
            end tell
            return ""
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=2)

            if 'dialog' in result.stdout:
                print("Share dialog detected, pressing Enter...")
                time.sleep(0.3)
                pyautogui.press('enter')
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            time.sleep(1)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--simple':
        simple_keyboard_approve()
    else:
        monitor_and_approve()
