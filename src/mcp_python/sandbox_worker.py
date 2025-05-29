# sandbox_worker.py
import sys, io, pickle, traceback, resource
from contextlib import redirect_stdout, redirect_stderr

# --- Hard limits -----------------------------------------------------------
resource.setrlimit(resource.RLIMIT_AS,  (256 * 1024 * 1024,)*2)   # 256 MB
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))                   # 5 s CPU
# --------------------------------------------------------------------------

# 1.  Read payload
payload = pickle.loads(sys.stdin.buffer.read())
code     = payload["code"]
context  = payload["context"]

# 2.  Capture user stdout / stderr
stdout_buf = io.StringIO()
stderr_buf = io.StringIO()

try:
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        exec(code, context)                      # <-- user code runs here
    # anything the user printed:
    captured_out  = stdout_buf.getvalue()
    captured_err  = stderr_buf.getvalue()

    # precedence: explicit `result` variable if they set one
    output = context.get("result")
    if output is None:                           # nothing in `result`
        output = captured_out or captured_err or "Code executed successfully."

except Exception:
    output = traceback.format_exc()

# 3.  Send back context + output
pickle.dump({"context": context, "output": str(output)}, sys.stdout.buffer)
