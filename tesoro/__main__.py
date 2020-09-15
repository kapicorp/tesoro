#!/usr/bin/env python3

from asyncio import Lock
import argparse
import logging
import ssl
from functools import partial

from aiohttp import web
from aiohttp.log import access_logger

from tesoro.handlers import healthz_handler, mutate_handler
from tesoro.metrics import prom_http_server
from tesoro.utils import setup_logging

setup_logging(kapitan_debug=False)
logger = logging.getLogger()

parser = argparse.ArgumentParser(description=("Tesoro" " - Kapitan Admission Controller"))
parser.add_argument("--verbose", action="store_true", default=False)
parser.add_argument("--verbose-no-redact", action="store_true", default=False)
parser.add_argument("--verbose-kapitan", action="store_true", default=False)
parser.add_argument("--access-log", action="store_true", default=False)
parser.add_argument("--port", action="store", type=int, default=8080)
parser.add_argument("--host", action="store", default="0.0.0.0")
parser.add_argument("--cert-file", action="store", default=None)
parser.add_argument("--key-file", action="store", default=None)
parser.add_argument("--ca-file", action="store", default=None)
parser.add_argument("--ca-path", action="store", default=None)
parser.add_argument("--metrics-port", action="store", type=int, default=9095)
parser.add_argument("--metrics-host", action="store", default="0.0.0.0")
args = parser.parse_args()
logger.info("Starting tesoro with args: %s", args)

if args.verbose:
    setup_logging(level=logging.DEBUG, kapitan_debug=args.verbose_kapitan)
    logger.debug("Logging level set to DEBUG")

reveal_lock = Lock()
app = web.Application()
app.add_routes(
    [
        web.get("/healthz", healthz_handler),
        web.post(
            "/mutate",
            partial(mutate_handler, reveal_lock=reveal_lock, log_redact_patch=(not args.verbose_no_redact)),
        ),
    ]
)

ssl_ctx = None
if None not in (args.key_file, args.cert_file):
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=args.ca_file, capath=args.ca_path)
    ssl_ctx.load_cert_chain(args.cert_file, args.key_file)

access_log = None
if args.access_log:
    access_log = access_logger

prom_http_server(args.metrics_port, args.metrics_host)
web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_ctx, access_log=access_log)
