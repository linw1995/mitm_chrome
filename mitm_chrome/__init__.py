# Standard Library
import argparse
import asyncio
import asyncio.subprocess
import logging
import socket
import sys
import tempfile
from contextlib import closing

# Third Party Library
from mitmproxy.tools._main import mitmdump, mitmproxy, mitmweb

logger = logging.getLogger(__name__)


def get_unused_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chrome-path", default="chrome", help="chrome executable path"
    )
    parser.add_argument("-ph", "--proxy-host", default="localhost", help="proxy host")
    parser.add_argument("-pp", "--proxy-port", type=int, help="proxy port")
    parser.add_argument("--cdp-port", type=int, help="enable chrome devtools")
    parser.add_argument("--user-data-dir", help="chrome user data dir")
    parser.add_argument(
        "command",
        help="launch chrome with",
        default="config",
        choices=["config", "mitmproxy", "mitmdump", "mitmweb"],
    )
    return parser


async def log_proc_output(
    proc: asyncio.subprocess.Process, logger: logging.Logger = None
):
    if logger is None:
        logger = logging.getLogger(__name__)

    async def log_output(reader: asyncio.StreamReader, name: str):
        assert logger is not None
        output = await reader.readline()
        logger.debug("%r %s: %s", proc, name, output.decode())

    log_stdout = log_stderr = None
    while proc.returncode is None:
        if log_stdout is None or log_stdout.done():
            assert proc.stdout is not None
            log_stdout = asyncio.ensure_future(log_output(proc.stdout, "stdout"))
        if log_stderr is None or log_stderr.done():
            assert proc.stderr is not None
            log_stderr = asyncio.ensure_future(log_output(proc.stderr, "stderr"))

        await asyncio.wait(
            [log_stderr, log_stdout],
            timeout=1,
            return_when=asyncio.FIRST_COMPLETED,
        )

    if log_stderr:
        log_stderr.cancel()

    if log_stdout:
        log_stdout.cancel()


async def launch_browser(
    chrome_path,
    proxy_host,
    proxy_port,
    cdp_port=None,
    user_data_dir=None,
):
    args = [
        f"--proxy-server={proxy_host}:{proxy_port}",
        "--no-first-run",
    ]
    if cdp_port is not None:
        args.append(f"--remote-debugging-port={cdp_port}")

    async def _launch_browser():
        proc: asyncio.Process = await asyncio.create_subprocess_exec(
            chrome_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("browser launched, proc %r", proc)
        try:
            await log_proc_output(proc)
        finally:
            proc.terminate()

    if user_data_dir is None:
        with tempfile.TemporaryDirectory() as user_data_dir:
            args.append(f"--user-data-dir={user_data_dir}")
            await _launch_browser()
    else:
        args.append(f"--user-data-dir={user_data_dir}")
        await _launch_browser()


def cli(args=None, namespace=None):
    parser = create_parser()
    args, unknown = parser.parse_known_args(args, namespace)
    if args.proxy_port is None:
        if args.command == "config":
            parser.error("config requires port")

        args.proxy_port = get_unused_port()

    logger.info("proxy config %r", args)

    coro = launch_browser(
        args.chrome_path,
        args.proxy_host,
        args.proxy_port,
        args.cdp_port,
        args.user_data_dir,
    )
    if args.command == "config":
        return asyncio.get_event_loop().run_until_complete(coro)

    asyncio.ensure_future(coro)
    if args.command == "mitmproxy":
        run_mitm = mitmproxy
    elif args.command == "mitmdump":
        run_mitm = mitmdump
    elif args.command == "mitmweb":
        run_mitm = mitmweb

    exit_code = run_mitm(args=["--listen-port", str(args.proxy_port)] + unknown)
    sys.exit(exit_code)
