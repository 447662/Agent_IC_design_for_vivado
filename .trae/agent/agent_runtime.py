import subprocess


class CommandRunner:
    def __init__(self, default_timeout=120):
        self.default_timeout = int(default_timeout)

    @staticmethod
    def _coerce_text(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def run(self, command, timeout=None, **kwargs):
        effective_timeout = self.default_timeout if timeout is None else int(timeout)
        kwargs["timeout"] = effective_timeout
        if kwargs.get("text") or kwargs.get("universal_newlines"):
            kwargs.setdefault("encoding", "utf-8")
            kwargs.setdefault("errors", "replace")
        try:
            return subprocess.run(command, **kwargs)
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_text(exc.stdout or exc.output)
            timeout_message = "Command timed out after {} seconds: {}".format(
                effective_timeout,
                " ".join(str(part) for part in command),
            )
            stderr = self._coerce_text(exc.stderr)
            if stderr:
                timeout_message = "{}\n{}".format(timeout_message, stderr)
            return subprocess.CompletedProcess(
                command,
                124,
                stdout=stdout,
                stderr=timeout_message,
            )

    def launch(self, command, **kwargs):
        return subprocess.Popen(command, **kwargs)


class TargetHandler:
    def __init__(self, target_name, flows):
        self.target_name = target_name
        self.flows = dict(flows)

    def run(self, flow, **kwargs):
        handler = self.flows.get(flow)
        if handler is None:
            raise ValueError(
                "Target {} does not support flow: {}".format(self.target_name, flow)
            )
        return handler(**kwargs)
