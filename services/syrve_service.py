import datetime
import logging
from typing import Any, Dict, Optional

import requests

# Set up logging
logger = logging.getLogger(__name__)


class SyrveService:
    """Service for interacting with Syrve ERP API"""

    def __init__(self, login: str, password: str, base_url: str):
        """
        Initialize Syrve service

        Args:
            login: Syrve API login
            password: Syrve API password
            base_url: Base URL for Syrve API
        """
        self.login = login
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.token_expiry = None
        logger.info(f"Syrve Service initialized with base URL: {base_url}")

    async def authenticate(self) -> bool:
        """
        Authenticate with Syrve API and get access token

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # Check if we have a valid token
            if self.token and self.token_expiry and datetime.datetime.now() < self.token_expiry:
                logger.debug("Using existing Syrve token")
                return True

            # Prepare authentication data
            auth_data = {"login": self.login, "password": self.password}

            # Send authentication request
            logger.info("Authenticating with Syrve API")
            response = requests.post(f"{self.base_url}/auth/login", json=auth_data, timeout=10)

            # Check response
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")

                # Set token expiry (typically 24 hours)
                self.token_expiry = datetime.datetime.now() + datetime.timedelta(hours=23)

                logger.info("Successfully authenticated with Syrve API")
                return True
            else:
                logger.error(
                    f"Failed to authenticate with Syrve API: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error authenticating with Syrve API: {str(e)}", exc_info=True)
            return False

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new invoice in Syrve

        Args:
            invoice_data: Invoice data to create

        Returns:
            str: Invoice ID if successful, None otherwise
        """
        try:
            # Authenticate if needed
            if not await self.authenticate():
                logger.error("Failed to authenticate with Syrve API")
                return None

            # Prepare headers
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

            # Prepare invoice data for Syrve format
            syrve_invoice = self._format_invoice_for_syrve(invoice_data)

            # Send request to create invoice
            logger.info("Creating invoice in Syrve")
            response = requests.post(
                f"{self.base_url}/documents/incoming",
                headers=headers,
                json=syrve_invoice,
                timeout=15,
            )

            # Check response
            if response.status_code in (200, 201):
                data = response.json()
                invoice_id = data.get("id")
                logger.info(f"Successfully created invoice in Syrve with ID: {invoice_id}")
                return invoice_id
            else:
                logger.error(
                    f"Failed to create invoice in Syrve: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error creating invoice in Syrve: {str(e)}", exc_info=True)
            return None

    def _format_invoice_for_syrve(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format invoice data for Syrve API

        Args:
            invoice_data: Raw invoice data

        Returns:
            dict: Formatted invoice data for Syrve
        """
        # Extract basic invoice info
        date = invoice_data.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
        vendor_name = invoice_data.get("vendor_name", "Unknown Vendor")
        total_amount = invoice_data.get("total_amount", 0)

        # Format items
        items = []
        for item in invoice_data.get("items", []):
            items.append(
                {
                    "product": {"id": item.get("product_id", ""), "name": item.get("name", "")},
                    "quantity": float(item.get("quantity", 1)),
                    "price": float(item.get("price", 0)),
                }
            )

        # Create Syrve invoice format
        syrve_invoice = {
            "date": date,
            "vendor": {"name": vendor_name},
            "items": items,
            "total": float(total_amount),
        }

        return syrve_invoice
