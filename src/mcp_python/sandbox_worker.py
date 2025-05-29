# sandbox_worker.py
import sys
import io
import pickle
import resource
import traceback
import types
from contextlib import redirect_stdout, redirect_stderr

# ── Resource limits ────────────────────────────────────────────────────────
resource.setrlimit(resource.RLIMIT_AS,  (256 * 1024 * 1024,) * 2)   # 256 MB
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))                     # 5 s CPU
# ───────────────────────────────────────────────────────────────────────────

# 1. Receive payload from parent
payload  = pickle.loads(sys.stdin.buffer.read())
code     = payload["code"]
context  = payload["context"]

# 2. Run user code with stdout / stderr captured
stdout_buf = io.StringIO()
stderr_buf = io.StringIO()

try:
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        exec(code, context)                       # user code executes here

    captured_out = stdout_buf.getvalue()
    captured_err = stderr_buf.getvalue()

    # Priority: an explicit `result` variable, else captured stdout / stderr,
    # else a generic success message
    output = context.get("result")
    if output is None:
        output = captured_out or captured_err or "Code executed successfully."

except Exception:
    output = traceback.format_exc()

# 3.  Strip un-picklable objects (modules, handles, etc.) from context
safe_ctx = {}
for k, v in context.items():
    if k == "__builtins__":           # never send built-ins
        continue
    if isinstance(v, types.ModuleType):
        continue                      # skip imported modules
    try:
        pickle.dumps(v)               # test picklability
    except Exception:
        continue
    safe_ctx[k] = v

# 4.  Send back the safe context and output
pickle.dump({"context": safe_ctx, "output": str(output)}, sys.stdout.buffer)
