#!/usr/bin/env python3

import argparse
import asyncio
from aiohttp import web
from aiohttp.log import access_logger
from base64 import b64encode, b64decode
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

    labels = kapicorp_labels(req_obj)

    if labels.get("kapicorp.com/tesoro", None) == "enabled":
        try:
            logger.debug("Request Uid: %s Namespace: %s Kind: %s Resource: %s",
                         req_uid, req_namespace, req_kind, req_resource)
            req_copy = deepcopy(req_obj)
            obj_kind = req_obj["kind"]

            transformations = prepare_obj(req_copy, obj_kind)
            logger.debug("Tranformations: %s", transformations)

            reveal_req_func = lambda: kapitan_reveal_json(req_copy)
            req_revealed = await run_blocking(reveal_req_func)
            transform_obj(req_revealed, transformations)
            patch = make_patch(req_obj, req_revealed)
            annotate_patch(patch)
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
        # not labelled, default allow
        return make_response(req_uid, [], allow=True)

    TESORO_FAILED_COUNTER.inc()
    return web.Response(status=500, reason='Unknown error')


def transform_obj(req_obj, transformations):
    "updates req_obj with transformations"
    secret_tranformations = transformations.get("Secret", {})
    secret_data_items = secret_tranformations.get("data", {}).items()
    for item_name, transform in secret_data_items:
        encoding = transform.get("encoding", None)
        if encoding == 'original':
            item_value_encoded = b64encode(req_obj["data"][item_name].encode()).decode()
            req_obj["data"][item_name] = item_value_encoded


def prepare_obj(req_obj, obj_kind):
    """
    updates object and returns transformation operations
    on specific object kinds to perform post reveal
    """
    transformations = {}
    if obj_kind == "Secret":
        transformations["Secret"] = {"data": {}}
        for item_name, item_value in req_obj["data"].items():
            decoded_ref = b64decode(item_value).decode()
            logger.debug("Secret transformation: decoded_ref: %s", decoded_ref)

            # TODO use kapitan's ref pattern instead
            if not (decoded_ref.startswith('?{') and
                    decoded_ref.endswith('}')):
                continue  # this is not a ref, do nothing
            else:
                # peek and register ref's encoding
                ref_obj = REF_CONTROLLER[decoded_ref]
                transformations["Secret"]["data"][item_name] = {"encoding": ref_obj.encoding}
                # override with ref so we can reveal
                req_obj["data"][item_name] = decoded_ref

    return transformations


def kapicorp_labels(req_obj):
    "returns kapicorp labels dict for req_obj"
    labels = {}
    try:
        for label_key, label_value in req_obj["metadata"]["labels"].items():
            if label_key.startswith("kapicorp.com/"):
                labels[label_key] = label_value
    except KeyError:
        return labels

    return labels


def annotate_patch(patch):
    """
    if patch not empty, annotates patch with list of revealed paths
    e.g. 'kapicorp.com/tesoro: revealed: ["/spec/templates/key1"]'
    """
    revealed_paths = []

    for p in patch:
        path = p.get("path")
        if path:
            revealed_paths.append(path)

    if revealed_paths:
        patch.append({
            "op": "add",
            "path": "/metadata/annotations/kapicorp.com~1tesoro",
            "value": "revealed: "+", ".join(revealed_paths)
        })


def make_patch(src_json, dst_json):
    "returns jsonpatch for diff between src_json and dst_json"
    patch = jsonpatch.make_patch(src_json, dst_json)
    patch = patch.patch

    last_applied = ('/metadata/annotations/'
                    'kubectl.kubernetes.io~1last-applied-configuration')

    # remove last_applied from patch if found (meaning it was revealed)
    # as we don't want to interfer with previous state
    for idx, patch_item in enumerate(patch):
        if patch_item['path'] == last_applied:
            patch.pop(idx)
            logger.debug("Removed last-applied-configuration annotation"
                         "from patch")

    return patch


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
