import unittest
from base64 import b64encode
from tesoro import REF_CONTROLLER
from tesoro.transform import prepare_obj, transform_obj


class TestPreprare(unittest.TestCase):
    def test_prepare_obj_k8s_secret(self):
        ref_tag = (
            "?{base64:eyJkYXRhIjogImNtVm1JREVnWkdGMFlRP"
            "T0iLCAiZW5jb2RpbmciOiAib3JpZ2luYWwiLCAidHl"
            "wZSI6ICJiYXNlNjQifQ==:embedded}"
        )
        k8s_obj = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "some-secret", "labels": {"tesoro.kapicorp.com": "enabled"},},
            "type": "Opaque",
            "data": {"file1": b64encode(bytes(ref_tag.encode())),},
        }
        transformations = prepare_obj("request_uid", k8s_obj)

        self.assertEqual(transformations, {"Secret": {"data": {"file1": {"encoding": "original"}}}})
        self.assertEqual(k8s_obj["data"]["file1"], ref_tag)

    def test_prepare_obj_k8s_other_obj(self):
        k8s_obj = {
            "apiVersion": "v1",
            "kind": "NotAsecret",
        }
        transformations = prepare_obj("request_uid", k8s_obj)

        self.assertEqual(transformations, {})


class TestTransform(unittest.TestCase):
    def test_transform_obj_k8s_secret_original_encoding(self):
        # base64 tag with encoding: original
        ref_tag = (
            "?{base64:eyJkYXRhIjogImNtVm1JREVnWkdGMFlRP"
            "T0iLCAiZW5jb2RpbmciOiAib3JpZ2luYWwiLCAidHl"
            "wZSI6ICJiYXNlNjQifQ==:embedded}"
        )
        k8s_obj = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "some-secret", "labels": {"tesoro.kapicorp.com": "enabled"},},
            "type": "Opaque",
            "data": {"file1": b64encode(bytes(ref_tag.encode())),},
        }
        transformations = prepare_obj("request_uid", k8s_obj)
        # reveal base64_ref
        ref_obj = REF_CONTROLLER[ref_tag]
        ref_obj_revealed = ref_obj.reveal()
        k8s_obj["data"]["file1"] = ref_obj_revealed

        transform_obj(k8s_obj, transformations)

        self.assertEqual(k8s_obj["data"]["file1"], b64encode(ref_obj_revealed.encode()).decode())

    def test_transform_obj_k8s_secret_base64_encoding(self):
        # base64 tag with encoding: base64 - needs kapitan 0.28+
        ref_tag = (
            "?{base64:eyJkYXRhIjogIllVZFdjMkpIT0QwPSIsICJlbmNvZGluZyI"
            "6ICJiYXNlNjQiLCAidHlwZSI6ICJiYXNlNjQifQ==:embedded}"
        )
        k8s_obj = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "some-secret", "labels": {"tesoro.kapicorp.com": "enabled"},},
            "type": "Opaque",
            "data": {"file1": b64encode(bytes(ref_tag.encode())),},
        }
        transformations = prepare_obj("request_uid", k8s_obj)
        # reveal base64_ref
        ref_obj = REF_CONTROLLER[ref_tag]
        ref_obj_revealed = ref_obj.reveal()
        k8s_obj["data"]["file1"] = ref_obj_revealed

        transform_obj(k8s_obj, transformations)

        self.assertEqual(k8s_obj["data"]["file1"], ref_obj_revealed)
