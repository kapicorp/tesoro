#!/usr/bin/env python3

import argparse
import asyncio
from aiohttp import web
from aiohttp.log import access_logger
from base64 import b64encode
from copy import deepcopy
import json
import jsonpatch
from kapitan.refs.base import RefController, Revealer
import logging
from prometheus_client import start_http_server as prom_http_server, Counter
import ssl


def setup_logging(level=logging.INFO):
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                        level=level,
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger('tesoro').setLevel(level)


setup_logging()
logger = logging.getLogger('tesoro')

ROUTES = web.RouteTableDef()

REF_CONTROLLER = RefController('/tmp', embed_refs=True)
REVEALER = Revealer(REF_CONTROLLER)

TESORO_COUNTER = Counter('tesoro_requests', 'Tesoro requests')
TESORO_FAILED_COUNTER = Counter('tesoro_requests_failed',
                                'Tesoro failed requests')
REVEAL_COUNTER = Counter('kapitan_reveal_requests',
                         'Kapitan reveal requests')
REVEAL_FAILED_COUNTER = Counter('kapitan_reveal_requests_failed',
                                'Kapitan reveal failed requests ')


@ROUTES.get('/healthz')
async def healthz(request):
    return web.Response(status=200, text='ok')


@ROUTES.post('/mutate')
async def mutate_handler(request):
    TESORO_COUNTER.inc()
    req_obj = {}
    req_uid = None
    req_namespace: None
    req_kind: None
    req_resource: None

    try:
        req_json = await request.json()
        req_uid = req_json["request"]["uid"]
        req_namespace = req_json["request"]["namespace"]
        req_kind = req_json["request"]["kind"]
        req_resource = req_json["request"]["resource"]
        req_obj = req_json["request"]["object"]
    except json.decoder.JSONDecodeError:
        TESORO_FAILED_COUNTER.inc()
        return web.Response(status=500, reason='Request not JSON')
    except KeyError:
        TESORO_FAILED_COUNTER.inc()
        return web.Response(status=500, reason='Invalid JSON request')

    annotations = kapicorp_annotations(req_obj)

    if annotations.get("kapicorp.com/tesoro", None) == "kapitan-reveal-refs":
        try:
            logger.debug("Request Uid: %s Namespace: %s Kind: %s Resource: %s",
                         req_uid, req_namespace, req_kind, req_resource)
            req_copy = deepcopy(req_obj)

            reveal_req_func = lambda: kapitan_reveal_json(req_copy)
            req_revealed = await run_blocking(reveal_req_func)
            patch = make_patch(req_obj, req_revealed)
            REVEAL_COUNTER.inc()
            logger.debug("Kapitan reveal successful, allowed with patch: %s",
                         patch)
            return make_response(req_uid, patch, allow=True)
        except Exception as e:
            logger.debug("Got exception error: %s %s", type(e), str(e))
            logger.debug("Kapitan reveal failed, disallowed")
            REVEAL_FAILED_COUNTER.inc()
            return make_response(req_uid, [], allow=False,
                                 message="Kapitan reveal failed")
    else:
        # not annotated, default allow
        return make_response(req_uid, [], allow=True)

    TESORO_FAILED_COUNTER.inc()
    return web.Response(status=500, reason='Unknown error')


def kapicorp_annotations(req_obj):
    "returns kapicorp annotations dict for req_obj"
    annotations = {}
    try:
        for anno_key, anno_value in req_obj["metadata"]["annotations"].items():
            if anno_key.startswith("kapicorp.com/"):
                annotations[anno_key] = anno_value
    except KeyError:
        return annotations

    return annotations


def make_patch(src_json, dst_json):
    "returns jsonpatch for diff between src_json and dst_json"
    p = jsonpatch.make_patch(src_json, dst_json)
    return p.patch


def make_response(uid, patch, allow=False, message=""):
    "returns new response with patch, allow and message"
    response = {"response": {"uid": uid, "allowed": allow}}

    if allow and (patch != []):
        patch_json = json.dumps(patch)
        b64_patch = b64encode(patch_json.encode()).decode()
        response["response"]["patchType"] = "JSONPatch"
        response["response"]["patch"] = b64_patch

    if message:
        response["response"]["status"] = {"message": message}

    return web.json_response(response)


async def run_blocking(func):
    "run blocking funcion in async executor"
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)


def kapitan_reveal_json(json_doc):
    "return revealed object, total revealed tags (TODO)"
    return REVEALER.reveal_obj(json_doc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=('Tesoro'
                                     ' - Kapitan Admission Controller'))
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--access-log', action='store_true', default=False)
    parser.add_argument('--port', action='store', type=int, default=8080)
    parser.add_argument('--host', action='store', default='0.0.0.0')
    parser.add_argument('--cert-file', action='store', default=None)
    parser.add_argument('--key-file', action='store', default=None)
    parser.add_argument('--ca-file', action='store', default=None)
    parser.add_argument('--ca-path', action='store', default=None)
    parser.add_argument('--metrics-port', action='store', type=int,
                        default=9095)
    parser.add_argument('--metrics-host', action='store', default='0.0.0.0')
    args = parser.parse_args()
    logger.info("Starting tesoro with args: %s", args)

    if args.verbose:
        setup_logging(level=logging.DEBUG)
        logger.debug("Logging level set to DEBUG")

    app = web.Application()
    app.add_routes(ROUTES)

    ssl_ctx = None
    if None not in (args.key_file, args.cert_file):
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH,
                                             cafile=args.ca_file,
                                             capath=args.ca_path)
        ssl_ctx.load_cert_chain(args.cert_file, args.key_file)

    access_log = None
    if args.access_log:
        access_log = access_logger

    prom_http_server(args.metrics_port, args.metrics_host)
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_ctx,
                access_log=access_log)
