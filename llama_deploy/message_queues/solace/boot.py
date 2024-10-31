import os
from logging import getLogger
from typing import Any, Dict, List, Literal, TYPE_CHECKING

# if TYPE_CHECKING:
from solace.messaging.config.solace_properties import (
    transport_layer_properties,
    service_properties,
    authentication_properties
)

# Constants
SOLBROKER_PROPERTIES_KEY = 'solbrokerProperties'
HOST_SECURED = 'solace.messaging.transport.host.secured'
HOST_COMPRESSED = 'solace.messaging.transport.host.compressed'
SEMP_HOSTNAME_KEY = 'solace.semp.hostname'
SEMP_USERNAME_KEY = 'solace.semp.username'
SEMP_PASSWORD_KEY = 'solace.semp.password'
SEMP_PORT_TO_CONNECT = '1943'
VALID_CERTIFICATE_AUTHORITY = 'public_root_ca'
IS_QUEUE_TEMPORARY = 'IS_QUEUE_TEMPORARY'

# Configure logger
logger = getLogger(__name__)

class BootSolace:
    """Class for instantiating the broker properties from environment."""

    @staticmethod
    def read_solbroker_props() -> dict:
        """Reads Solbroker properties from environment variables."""
        broker_properties = {
            transport_layer_properties.HOST: os.getenv('SOLACE_HOST'),
            service_properties.VPN_NAME: os.getenv('SOLACE_VPN_NAME'),
            authentication_properties.SCHEME_BASIC_USER_NAME: os.getenv('SOLACE_USERNAME'),
            authentication_properties.SCHEME_BASIC_PASSWORD: os.getenv('SOLACE_PASSWORD'),
            HOST_SECURED: os.getenv('SOLACE_HOST_SECURED'),
            HOST_COMPRESSED: os.getenv('SOLACE_HOST_COMPRESSED'),
            IS_QUEUE_TEMPORARY: os.getenv('SOLACE_IS_QUEUE_TEMPORARY').lower() in ['true', '1', 'yes'],
        }

        # Validate required properties
        required_keys = [
            transport_layer_properties.HOST,
            service_properties.VPN_NAME,
            authentication_properties.SCHEME_BASIC_USER_NAME,
            authentication_properties.SCHEME_BASIC_PASSWORD,
            HOST_SECURED,
        ]

        missing_keys = [key for key in required_keys if broker_properties[key] is None]
        if missing_keys:
            logger.warning(f'Missing required Solbroker properties: {missing_keys}')
            return {}

        logger.info(
            f"\n\n********************************BROKER PROPERTIES**********************************************"
            f"\nHost: {broker_properties.get(transport_layer_properties.HOST)}"
            f"\nSecured Host: {broker_properties.get(HOST_SECURED)}"
            f"\nCompressed Host: {broker_properties.get(HOST_COMPRESSED)}"
            f"\nVPN: {broker_properties.get(service_properties.VPN_NAME)}"
            f"\nUsername: {broker_properties.get(authentication_properties.SCHEME_BASIC_USER_NAME)}"
            f"\nPassword: <hidden>"
            f"\nIs Queue Temporary: {broker_properties.get(IS_QUEUE_TEMPORARY)}"
            f"\n***********************************************************************************************\n"
        )
        return broker_properties

    @staticmethod
    def broker_properties() -> dict:
        """Reads the Solbroker properties from environment variables."""
        try:
            props = BootSolace.read_solbroker_props()
            return props
        except Exception as exception:
            logger.error(f"Unable to read broker properties. Exception: {exception}")
            raise
