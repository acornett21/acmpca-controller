# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the ACMPCA Certificate Authority resource.
"""

import time
import logging
from typing import Dict, Tuple

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_acmpca_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.tests.helper import ACMPCAValidator

RESOURCE_PLURAL = "certificateauthorities"

CREATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10

@service_marker
class TestCertificateAuthority:

    def test_create_delete(self, acmpca_client):
        ca_name = random_suffix_name("certificate-authority", 24)
        replacements = REPLACEMENT_VALUES.copy()
        replacements["NAME"] = ca_name
        replacements["COMMON_NAME"] = "www.example.com"
        replacements["COUNTRY"] = "US"
        replacements["LOCALITY"] = "Arlington"
        replacements["ORG"] = "Example Organization"
        replacements["STATE"] = "Virginia"

        # Load CA CR
        resource_data = load_acmpca_resource(
            "certificate_authority",
            additional_replacements=replacements,
        )
        logging.info(resource_data)

        # Create k8s resource
        ref = k8s.create_reference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            ca_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        assert cr is not None
        assert k8s.get_resource_exists(ref)

        resource = k8s.get_resource(ref)
        assert resource is not None

        resource_arn =  k8s.get_resource_arn(cr)
        assert resource_arn is not None

        # Check CA status is PENDING_CERTIFICATE
        acmpca_validator = ACMPCAValidator(acmpca_client)
        ca = acmpca_validator.assert_certificate_authority(resource_arn, "PENDING_CERTIFICATE")

        # Check CA fields
        assert ca["Type"] == "ROOT"
        assert ca["CertificateAuthorityConfiguration"]["Subject"]["CommonName"] == "www.example.com"
        assert ca["CertificateAuthorityConfiguration"]["Subject"]["Country"] == "US"
        assert ca["CertificateAuthorityConfiguration"]["Subject"]["Locality"] == "Arlington"
        assert ca["CertificateAuthorityConfiguration"]["Subject"]["Organization"] == "Example Organization"
        assert ca["CertificateAuthorityConfiguration"]["Subject"]["State"] == "Virginia"
        assert ca["CertificateAuthorityConfiguration"]["KeyAlgorithm"] == "RSA_2048"
        assert ca["CertificateAuthorityConfiguration"]["SigningAlgorithm"] == "SHA256WITHRSA"

        # Check Tags
        acmpca_validator.assert_ca_tags(resource_arn, "tag1", "val1")

        # Check CSR
        assert 'status' in cr
        assert 'certificateSigningRequest' in cr['status']
        csr = acmpca_validator.get_csr(resource_arn)
        assert cr['status']['certificateSigningRequest'] == csr

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check CA status is DELETED
        acmpca_validator.assert_certificate_authority(resource_arn, "DELETED")