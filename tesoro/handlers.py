from base64 import b64encode
from copy import deepcopy
import json
import logging
from sys import exc_info
from aiohttp import web
from tesoro.metrics import TESORO_COUNTER, TESORO_FAILED_COUNTER, REVEAL_COUNTER, REVEAL_FAILED_COUNTER
from tesoro.patch import make_patch, annotate_patch, redact_patch
from tesoro.transform import prepare_obj, transform_obj
from tesoro.utils import kapicorp_labels, run_blocking, kapitan_reveal_json, KapitanRevealFail

logger = logging.getLogger(__name__)


async def healthz_handler(request):
    return web.Response(status=200, text="ok")


async def mutate_handler(request, log_redact_patch=True):
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
        req_obj_name = req_obj["metadata"]["name"]

    except json.decoder.JSONDecodeError:
        TESORO_FAILED_COUNTER.inc()
        return web.Response(status=500, reason="Request not JSON")
    except KeyError:
        TESORO_FAILED_COUNTER.inc()
        return web.Response(status=500, reason="Invalid JSON request")

    labels = kapicorp_labels(req_obj)

    if labels.get("tesoro.kapicorp.com", None) == "enabled":
        try:
            logger.debug(
                "Request Uid: %s, Namespace: %s, Kind: %s, Object Name: %s, Resource: %s",
                req_uid,
                req_namespace,
                req_kind,
                req_obj_name,
                req_resource,
            )
            req_copy = deepcopy(req_obj)

            transformations = prepare_obj(req_copy)
            logger.debug("Tranformations: %s", transformations)

            reveal_req_func = lambda: kapitan_reveal_json(req_copy)
            req_revealed = await run_blocking(reveal_req_func)
            if req_revealed is None:
                raise KapitanRevealFail("revealed object is None")

            transform_obj(req_revealed, transformations)
            patch = make_patch(req_obj, req_revealed)
            annotate_patch(patch)
            REVEAL_COUNTER.inc()
            if log_redact_patch:
                logger.debug("Kapitan reveal successful, allowed with patch: %s", redact_patch(patch))
            else:
                logger.debug("Kapitan reveal successful, allowed with patch: %s", patch)

            return make_response(req_uid, patch, allow=True)
        except Exception as e:
            exc_type, exc_value, _ = exc_info()
            logger.debug("Got exception: %s: %s", exc_type, exc_value)
            logger.debug("Kapitan reveal failed, disallowed")
            REVEAL_FAILED_COUNTER.inc()
            return make_response(req_uid, [], allow=False, message="Kapitan reveal failed")
    else:
        # not labelled, default allow
        return make_response(req_uid, [], allow=True)

    TESORO_FAILED_COUNTER.inc()
    return web.Response(status=500, reason="Unknown error")


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
