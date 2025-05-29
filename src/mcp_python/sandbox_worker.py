import sys
import resource
import pickle

# --- Set hard memory + CPU limits ---
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))  # 256MB memory
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))  # 5s CPU time

# --- Read input from parent process ---
data = sys.stdin.buffer.read()
payload = pickle.loads(data)
code = payload['code']
context = payload['context']

# --- Run code and capture output ---
stdout = []
try:
    exec(code, context)
    output = context.get('result', 'Code executed successfully.')
except Exception as e:
    output = f"Exception: {e}"

# --- Write back context and output ---
result = {'context': context, 'output': str(output)}
sys.stdout.buffer.write(pickle.dumps(result))
