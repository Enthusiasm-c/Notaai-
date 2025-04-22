import base64
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletion

# Set up logging
logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR processing using OpenAI Vision models"""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """
        Initialize OCR service

        Args:
            api_key: OpenAI API key
            model: Model to use for OCR (default: gpt-4o)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"OCR Service initialized with model: {model}")

    async def process_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Process an image using OpenAI Vision API

        Args:
            image_data: Raw image data

        Returns:
            dict: Structured data extracted from the image
        """
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Create the messages for the API call
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all information from this invoice. Return a JSON with fields: date, vendor_name, total_amount, items (array with name, quantity, price)",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ]

            # Call OpenAI API
            logger.info("Sending image to OpenAI for processing")
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model, messages=messages, response_format={"type": "json_object"}
            )

            # Extract the JSON content
            content = response.choices[0].message.content
            logger.info("Successfully processed image with OpenAI")

            # Parse and return the JSON
            return self._parse_response_content(content)

        except Exception as e:
            logger.error(f"Error processing image with OpenAI: {str(e)}", exc_info=True)
            raise

    def _parse_response_content(self, content: Optional[str]) -> Dict[str, Any]:
        """
        Parse response content into structured data

        Args:
            content: Response content from OpenAI

        Returns:
            dict: Structured data extracted from the response
        """
        import json

        if not content:
            logger.warning("Received empty content from OpenAI")
            return {}

        try:
            # Parse the JSON
            data = json.loads(content)

            # Validate and normalize the response
            if "items" in data and isinstance(data["items"], list):
                # Ensure all items have the required fields
                for item in data["items"]:
                    if "name" not in item:
                        item["name"] = ""
                    if "quantity" not in item:
                        item["quantity"] = 1
                    if "price" not in item:
                        item["price"] = 0

            logger.info(f"Extracted {len(data.get('items', []))} items from invoice")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Error processing OpenAI response: {str(e)}", exc_info=True)
            return {}
