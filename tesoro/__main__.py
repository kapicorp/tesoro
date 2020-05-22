#!/usr/bin/env python3

import argparse
import asyncio
from aiohttp import web
from base64 import b64encode
from copy import deepcopy
import json
import jsonpatch
from kapitan.refs.base import RefController, Revealer
import logging
from prometheus_client import start_http_server as prom_http_server, Counter
import ssl

logging.basicConfig(level=logging.INFO)

ROUTES = web.RouteTableDef()

REF_CONTROLLER = RefController('/tmp', embed_refs=True)
REVEALER = Revealer(REF_CONTROLLER)

TESORO_COUNTER = Counter('tesoro_requests', 'Tesoro requests')
TESORO_FAILED_COUNTER = Counter('tesoro_requests_failed', 'Tesoro failed requests')
REVEAL_COUNTER = Counter('kapitan_reveal_requests', 'Kapitan reveal ref requests')
REVEAL_FAILED_COUNTER = Counter('kapitan_reveal_requests_failed',
                                'Kapitan reveal ref failed requests ')


@ROUTES.post('/mutate/{resource}')
async def mutate_resource_handler(request):
    TESORO_COUNTER.inc()
    try:
        req_json = await request.json()
        # default to 500 unknown error
        response = web.Response(status=500, reason='Unknown error')

        # check for 'kapicorp.com/tesoro' annotations
        annotations = req_json["request"]["object"]["metadata"]["annotations"]
        annotation = annotations.get("kapicorp.com/tesoro", None)

        if annotation == "kapitan-reveal-refs":
            try:
                req_copy = deepcopy(req_json)
                reveal_req_func = lambda: kapitan_reveal_json(req_copy)
                req_revealed = await run_blocking(reveal_req_func)
                patch = make_patch(req_json, req_revealed)
                response = make_response(patch, allow=True)
                REVEAL_COUNTER.inc()

            except Exception as e:
                # TODO log exception error
                response = make_response([], allow=False,
                                         message="Kapitan Reveal Failed")
                REVEAL_FAILED_COUNTER.inc()
        else:
            # not annotated, default allow
            # TODO log success
            response = make_response([], allow=True)

    except json.decoder.JSONDecodeError:
        TESORO_FAILED_COUNTER.inc()
        return web.Response(status=500, reason='Request not JSON')

    return response


def make_patch(src_json, dst_json):
    p = jsonpatch.make_patch(src_json, dst_json)
    return p.patch


def make_response(patch, allow=False, message=""):
    patch_json = json.dumps(patch)
    b64_patch = b64encode(patch_json.encode()).decode()
    response = {
                "response": {
                    "allowed": allow,
                    "status": {"message": message},
                    "patchType": "JSONPatch",
                    "patch": b64_patch
                    }
                }
    return web.json_response(response)


async def run_blocking(func):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)


def kapitan_reveal_json(json_doc):
    "return revealed object, total revealed tags (TODO)"
    return REVEALER.reveal_obj(json_doc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tesoro - Kapitan Admission Controller')
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--port', action='store', type=int, default=8080)
    parser.add_argument('--host', action='store', default='0.0.0.0')
    parser.add_argument('--cert-file', action='store', default=None)
    parser.add_argument('--key-file', action='store', default=None)
    parser.add_argument('--ca-file', action='store', default=None)
    parser.add_argument('--ca-path', action='store', default=None)
    parser.add_argument('--metrics-port', action='store', type=int, default=9095)
    parser.add_argument('--metrics-host', action='store', default='0.0.0.0')
    args = parser.parse_args()

    app = web.Application()
    app.add_routes(ROUTES)

    ssl_ctx = None
    if None not in (args.key_file, args.cert_file):
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH,
                                             cafile=args.ca_file,
                                             capath=args.ca_path)
        ssl_ctx.load_cert_chain(args.cert_file, args.key_file)

    prom_http_server(args.metrics_port, args.metrics_host)
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_ctx)
