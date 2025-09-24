# Android GA Tracking Debugger
# Copyright (c) 2025 Alejandro Reinoso
#
# This software is licensed under the Custom Shared-Profit License (CSPL) v1.0.
# See the LICENSE.txt file for details.

import subprocess
import sys
import threading
from enum import Enum, auto

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# --- Verification Functions --- #


def check_adb_installed():
    """
    Checks whether ADB is installed by attempting to run 'adb version'.
    Returns: True if it can be executed, False otherwise.
    """
    try:
        subprocess.check_output(["adb", "version"],
                                stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def check_device_connected():
    """
    Runs 'adb devices' and determines if at least one device or emulator is connected.
    """
    try:
        result = subprocess.check_output(
            ["adb", "devices"], stderr=subprocess.STDOUT, universal_newlines=True,
            creationflags=CREATE_NO_WINDOW)
        lines = result.strip().split('\n')

        # The first line is usually: "List of devices attached"
        # Starting from the second, each line represents a device (id + state).
        if len(lines) > 1:
            # We filter out empty lines or those that begin with "* daemon"
            device_lines = [
                l for l in lines[1:]
                if l.strip() != '' and not l.startswith('* daemon')
            ]

            for dev in device_lines:
                parts = dev.split()
                # parts[0] = device ID, parts[1] = state
                if len(parts) >= 2:
                    state = parts[1].lower()
                    if state == "device":
                        return True
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        # If ADB is not installed or fails
        return False


# --- Class for Handling Errors --- #

class AdbError(Enum):
    MULTIPLE_DEVICES = auto()
    # DEVICE_OFFLINE = auto() # <-- Example of how to add more in the future

# --- Class to Manage Logcat ---


class LogcatManager:
    def __init__(self, log_queue, on_error_callback):
        self.log_queue = log_queue
        self.on_error_callback = on_error_callback
        self.logcat_process = None
        self.stop_event = threading.Event()
        self.stdout_thread = None
        self.stderr_thread = None

    def _read_stdout(self):
        """Reads lines from logcat stdout and pushes them into a queue"""
        while not self.stop_event.is_set() and self.logcat_process.poll() is None:
            line = self.logcat_process.stdout.readline()
            self.log_queue.put(line.rstrip('\n'))

    def _read_stderr(self):
        """Read the error output, looking for problems."""
        while not self.stop_event.is_set() and self.logcat_process.poll() is None:
            line_err = self.logcat_process.stderr.readline()
            if not line_err:
                break
            if "more than one device/emulator" in line_err.lower():
                self.on_error_callback(AdbError.MULTIPLE_DEVICES)
                self.stop()
                return

    def start(self):
        """Prepares and starts the logcat process and reader threads."""
        self.stop_event.clear()

        # Prepare the ADB environment
        subprocess.run(["adb", "shell", "setprop", "log.tag.FA",
                       "VERBOSE"], creationflags=CREATE_NO_WINDOW)
        subprocess.run(["adb", "shell", "setprop", "log.tag.FA-SVC",
                       "VERBOSE"], creationflags=CREATE_NO_WINDOW)
        subprocess.run(["adb", "logcat", "-c"], creationflags=CREATE_NO_WINDOW)

        # Start the logcat process
        self.logcat_process = subprocess.Popen(
            ["adb", "logcat", "-v", "time", "-s", "FA", "FA-SVC"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=CREATE_NO_WINDOW
        )

        # Start reading threads
        self.stdout_thread = threading.Thread(
            target=self._read_stdout, daemon=True)
        self.stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread.start()

        return True

    def stop(self):
        """Detiene los hilos y el proceso logcat."""
        if self.logcat_process and self.logcat_process.poll() is None:
            self.stop_event.set()
            self.logcat_process.terminate()
            # Wait for the process to actually finish
            try:
                self.logcat_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.logcat_process.kill()
            self.logcat_process = None
