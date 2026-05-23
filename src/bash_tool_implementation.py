import platform
import queue
import shlex
import subprocess
import threading
import time

ALLOWED_COMMANDS = {
    # Cross-platform
    "echo", "pwd",
    # Unix-style (also work as aliases in PowerShell)
    "ls", "cat", "grep", "find", "wc", "head", "tail",
    # Windows PowerShell native
    "dir", "type", "Get-ChildItem", "Get-Content", "Select-String",
    "Measure-Object", "Select-Object",
}
SHELL_OPERATORS = {"&&", "||", "|", ";", "&", ">", "<", ">>"}

_SENTINEL = "__CMD_DONE__"


def validate_command(command: str) -> tuple[bool, str | None]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False, "Could not parse command"

    if not tokens:
        return False, "Empty command"

    executable = tokens[0]
    if executable not in ALLOWED_COMMANDS:
        return False, f"Command '{executable}' is not in the allowlist"

    for token in tokens[1:]:
        if token in SHELL_OPERATORS or token.startswith(("$", "`")):
            return False, f"Shell operator '{token}' is not allowed"

    return True, None


class BashSession:
    def __init__(self):
        self.output_queue: queue.Queue = queue.Queue()
        self.error_queue: queue.Queue = queue.Queue()
        self.process = self._start_process()
        self._start_readers()

    def _shell_cmd(self) -> list[str]:
        if platform.system() == "Windows":
            return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"]
        return ["/bin/bash"]

    def _start_process(self) -> subprocess.Popen:
        return subprocess.Popen(
            self._shell_cmd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )

    def _start_readers(self) -> None:
        def read_stdout():
            for line in self.process.stdout:
                self.output_queue.put(line)

        def read_stderr():
            for line in self.process.stderr:
                self.error_queue.put(line)

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()

    def _read_output(self, timeout: float = 10.0) -> str:
        output_lines = []
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                line = self.output_queue.get(timeout=0.1)
                if _SENTINEL in line:
                    break
                output_lines.append(line)
            except queue.Empty:
                continue

        error_lines = []
        while not self.error_queue.empty():
            try:
                error_lines.append(self.error_queue.get_nowait())
            except queue.Empty:
                break

        output = "".join(output_lines).strip()
        errors = "".join(error_lines).strip()

        if errors:
            return f"{output}\nSTDERR: {errors}".strip()
        return output

    def execute_command(self, command: str) -> str:
        is_valid, error = validate_command(command)
        if not is_valid:
            return f"Command rejected: {error}"

        self.process.stdin.write(command + "\n")
        self.process.stdin.write(f'echo "{_SENTINEL}"\n')
        self.process.stdin.flush()

        return self._read_output(timeout=10)

    def restart(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()

        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.process = self._start_process()
        self._start_readers()
