import shlex
import shutil
import subprocess

ALLOWED_COMMANDS = {
    "echo", "pwd", "ls", "cat", "grep", "find", "wc", "head", "tail",
    "git", "mkdir", "rm", "rmdir", "cp", "mv", "cd", "dirname", "basename",
}
SHELL_OPERATORS = {"&&", "||", "|", ";", "&", ">", "<", ">>"}


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

    return True, None


def _find_shell() -> str | None:
    """Return bash if available on PATH, otherwise None to fall back to cmd.exe.
    wsl.exe is intentionally excluded — it exists on Windows even when WSL is not installed,
    causing misleading failures.
    """
    if shutil.which("bash"):
        return "bash"
    return None


class BashSession:
    def __init__(self):
        self._shell = _find_shell()

    def execute_command(self, command: str) -> str:
        is_valid, error = validate_command(command)
        if not is_valid:
            return f"Command rejected: {error}"

        try:
            if self._shell:
                result = subprocess.run(
                    [self._shell, "-c", command],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 10 seconds"
        except Exception as e:
            return f"Error: {e}"

        output = result.stdout.strip()
        errors = result.stderr.strip()

        if errors:
            return f"{output}\nSTDERR: {errors}".strip()
        return output

    def restart(self) -> None:
        """Re-detect available shell (no persistent process to restart)."""
        self._shell = _find_shell()
