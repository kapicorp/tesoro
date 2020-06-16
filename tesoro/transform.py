from base64 import b64encode, b64decode
from tesoro import REF_CONTROLLER

import logging

logger = logging.getLogger("tesoro")


def prepare_obj(req_obj):
    """
    updates object and returns transformation operations
    on specific object kinds to perform post reveal
    """
    transformations = {}
    obj_kind = req_obj["kind"]
    if obj_kind == "Secret":
        transformations["Secret"] = {"data": {}}
        for item_name, item_value in req_obj["data"].items():
            decoded_ref = b64decode(item_value).decode()
            logger.debug("Secret transformation: decoded_ref: %s", decoded_ref)

            # TODO use kapitan's ref pattern instead
            if not (decoded_ref.startswith("?{") and decoded_ref.endswith("}")):
                continue  # this is not a ref, do nothing
            else:
                # peek and register ref's encoding
                ref_obj = REF_CONTROLLER[decoded_ref]
                transformations["Secret"]["data"][item_name] = {"encoding": ref_obj.encoding}
                # override with ref so we can reveal
                req_obj["data"][item_name] = decoded_ref

    return transformations


def transform_obj(req_obj, transformations):
    "updates req_obj with transformations"
    secret_tranformations = transformations.get("Secret", {})
    secret_data_items = secret_tranformations.get("data", {}).items()
    for item_name, transform in secret_data_items:
        encoding = transform.get("encoding", None)
        if encoding == "original":
            item_value_encoded = b64encode(req_obj["data"][item_name].encode()).decode()
            req_obj["data"][item_name] = item_value_encoded
