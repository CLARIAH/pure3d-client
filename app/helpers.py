import sys

from files import unexpanduser as ux


def console(*msg, error=False, newline=True):
    msg = " ".join(m if type(m) is str else repr(m) for m in msg)
    msg = "" if not msg else ux(msg)
    msg = msg[1:] if msg.startswith("\n") else msg
    msg = msg[0:-1] if msg.endswith("\n") else msg
    target = sys.stderr if error else sys.stdout
    nl = "\n" if newline else ""
    target.write(f"{msg}{nl}")
    target.flush()
