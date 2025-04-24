"""
Service for interacting with Syrve ERP API
"""
import datetime
import logging
from typing import Any, Dict, Optional

import requests

# Set up logging
logger = logging.getLogger(__name__)

__all__ = ["SyrveService", "authenticate", "commit_document", "send_invoice_to_syrve"]


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


async def authenticate(login: str, password: str, base_url: str) -> bool:
    """
    Standalone function to authenticate with Syrve API
    
    Args:
        login: Syrve API login
        password: Syrve API password
        base_url: Base URL for Syrve API
        
    Returns:
        bool: True if authentication successful
    """
    service = SyrveService(login, password, base_url)
    return await service.authenticate()


async def commit_document(document_id: str, token: str, base_url: str) -> bool:
    """
    Commit a document in Syrve API
    
    Args:
        document_id: ID of the document to commit
        token: Authentication token
        base_url: Base URL for Syrve API
        
    Returns:
        bool: True if commit successful
    """
    logger.info(f"Committing document with ID: {document_id}")
    try:
        # Prepare headers
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Send request to commit document
        response = requests.post(
            f"{base_url}/documents/{document_id}/commit",
            headers=headers,
            timeout=10
        )
        
        # Check response
        if response.status_code in (200, 204):
            logger.info(f"Successfully committed document with ID: {document_id}")
            return True
        else:
            logger.error(f"Failed to commit document: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error committing document: {str(e)}", exc_info=True)
        return False


async def send_invoice_to_syrve(invoice_data: Dict[str, Any], login: str, password: str, base_url: str) -> Optional[str]:
    """
    Send invoice data to Syrve API
    
    Args:
        invoice_data: Invoice data to send
        login: Syrve API login
        password: Syrve API password
        base_url: Base URL for Syrve API
        
    Returns:
        str: Document ID if successful, None otherwise
    """
    logger.info("Sending invoice to Syrve")
    service = SyrveService(login, password, base_url)
    document_id = await service.create_invoice(invoice_data)
    
    if document_id:
        logger.info(f"Successfully created document with ID: {document_id}")
        return document_id
    else:
        logger.error("Failed to create document in Syrve")
        return None
