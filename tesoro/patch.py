from copy import deepcopy
from hashlib import sha256
import json
import jsonpatch
import logging

logger = logging.getLogger(__name__)


def annotate_patch(patch):
    """
    if patch not empty, annotates patch with list of revealed paths
    e.g. 'tesoro.kapicorp.com/revealed: ["/spec/templates/key1"]'
    """
    revealed_paths = []

    for p in patch:
        path = p.get("path")
        if path:
            revealed_paths.append(path)

    if revealed_paths:
        patch.append(
            {
                "op": "add",
                "path": "/metadata/annotations/tesoro.kapicorp.com~1revealed",
                "value": json.dumps(revealed_paths),
            }
        )


def make_patch(req_uid, src_json, dst_json):
    "returns jsonpatch for diff between src_json and dst_json"
    patch = jsonpatch.make_patch(src_json, dst_json)
    patch = patch.patch

    last_applied = "/metadata/annotations/" "kubectl.kubernetes.io~1last-applied-configuration"

    # remove last_applied from patch if found (meaning it was revealed)
    # as we don't want to interfer with previous state
    for idx, patch_item in enumerate(patch):
        if patch_item["path"] == last_applied:
            patch.pop(idx)
            logger.debug("message=\"Removed last-applied-configuration annotation from patch\", req_uid=%s", req_uid)

    return patch


def redact_patch(patch):
    "returns a copy of patch with redacted values"
    redacted_patch = deepcopy(patch)

    for patch_item in redacted_patch:
        # don't redact this annotation
        if patch_item["path"] == "/metadata/annotations/tesoro.kapicorp.com~1revealed":
            continue
        value_hash = sha256(patch_item["value"].encode()).hexdigest()
        patch_item["value"] = f"!REDACTED VALUE! sha256={value_hash}"

    return redacted_patch
