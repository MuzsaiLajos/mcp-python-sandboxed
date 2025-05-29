import asyncio
import io
import subprocess
import re
from contextlib import redirect_stdout, redirect_stderr
import traceback
import pickle
import signal
import sys
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

class PythonREPLServer:
    def __init__(self):
        self.server = Server("python-repl")
        self.global_namespace = {
            "__builtins__": __builtins__,
        }

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return await self.handle_list_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            return await self.handle_call_tool(name, arguments)

    async def handle_list_tools(self) -> list[types.Tool]:
        return [
            types.Tool(
                name="execute_python",
                description="Execute Python code and return the output. Variables persist between executions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute",
                        },
                        "reset": {
                            "type": "boolean",
                            "description": "Reset the Python session (clear all variables)",
                            "default": False
                        }
                    },
                    "required": ["code"],
                },
            ),
            types.Tool(
                name="list_variables",
                description="List all variables in the current session",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="install_package",
                description="Install a Python package using uv",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package": {
                            "type": "string",
                            "description": "Package name to install (e.g., 'pandas')",
                        }
                    },
                    "required": ["package"],
                },
            )
        ]

    async def handle_call_tool(self, name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        if not arguments:
            raise ValueError("Missing arguments")

        if name == "execute_python":
            code = arguments.get("code")
            if not code:
                raise ValueError("Missing code parameter")

            if arguments.get("reset", False):
                self.global_namespace.clear()
                self.global_namespace["__builtins__"] = __builtins__
                return [
                    types.TextContent(type="text", text="Python session reset. All variables cleared.")
                ]

            try:
                state = {k: v for k, v in self.global_namespace.items() if k != "__builtins__"}
                input_data = pickle.dumps({'code': code, 'context': state})

                try:
                    proc = subprocess.Popen(
                        [sys.executable, 'sandbox_worker.py'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    out, err = proc.communicate(input=input_data, timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out, err = proc.communicate()
                    return [types.TextContent(type="text", text="Error: Code execution timed out after 15 seconds.")]
                except Exception:
                    return [types.TextContent(type="text", text=f"Error executing code:\n{traceback.format_exc()}")]

                if proc.returncode != 0:
                    return [types.TextContent(type="text", text=f"Error: {err.decode()}")]

                result = pickle.loads(out)
                self.global_namespace.update(result.get('context', {}))
                output = result.get('output', '')
                return [types.TextContent(type="text", text=output)]

            except Exception:
                return [types.TextContent(type="text", text=f"Error executing code:\n{traceback.format_exc()}")]

        elif name == "install_package":
            package = arguments.get("package")
            if not package:
                raise ValueError("Missing package name")

            if not re.match("^[A-Za-z0-9][A-Za-z0-9._-]*$", package):
                return [types.TextContent(type="text", text=f"Invalid package name: {package}")]

            try:
                process = subprocess.run(
                    ["uv", "pip", "install", package],
                    capture_output=True,
                    text=True,
                    check=True
                )
                exec(f"import {package.split('[')[0]}", self.global_namespace)
                return [types.TextContent(type="text", text=f"Successfully installed and imported {package}")]
            except subprocess.CalledProcessError as e:
                return [types.TextContent(type="text", text=f"Failed to install package:\n{e.stderr}")]
            except ImportError as e:
                return [types.TextContent(type="text", text=f"Package installed but import failed: {str(e)}")]

        elif name == "list_variables":
            vars_dict = {k: repr(v) for k, v in self.global_namespace.items() if not k.startswith('_') and k != '__builtins__'}
            if not vars_dict:
                return [types.TextContent(type="text", text="No variables in current session.")]
            var_list = "\n".join(f"{k} = {v}" for k, v in vars_dict.items())
            return [types.TextContent(type="text", text=f"Current session variables:\n\n{var_list}")]

        else:
            raise ValueError(f"Unknown tool: {name}")

    async def run(self):
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="python-repl",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

async def main():
    server = PythonREPLServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
