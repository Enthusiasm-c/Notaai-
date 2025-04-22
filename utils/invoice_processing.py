import logging
import re
from typing import Dict, Any, List
import datetime

from utils.match import match, get_product_by_id
from utils.learning import get_product_id_from_mapping

# Set up logging
logger = logging.getLogger(__name__)

def process_invoice_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process raw OCR data into structured invoice data
    
    Args:
        raw_data: Raw data from OCR
        
    Returns:
        dict: Processed invoice data
    """
    # Initialize processed data
    processed_data = {
        "date": raw_data.get("date", datetime.datetime.now().strftime("%Y-%m-%d")),
        "vendor_name": raw_data.get("vendor_name", "Unknown Vendor"),
        "total_amount": raw_data.get("total_amount", 0),
        "items": []
    }
    
    # Clean and normalize date
    processed_data["date"] = normalize_date(processed_data["date"])
    
    # Clean vendor name
    processed_data["vendor_name"] = clean_vendor_name(processed_data["vendor_name"])
    
    # Normalize total amount
    processed_data["total_amount"] = normalize_amount(processed_data["total_amount"])
    
    # Process items
    raw_items = raw_data.get("items", [])
    processed_items = []
    
    for item in raw_items:
        processed_item = process_item(item)
        if processed_item:
            processed_items.append(processed_item)
    
    processed_data["items"] = processed_items
    
    logger.info(f"Processed invoice with {len(processed_items)} items from {processed_data['vendor_name']}")
    return processed_data

def normalize_date(date_str: str) -> str:
    """
    Normalize date strings to YYYY-MM-DD format
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        str: Normalized date string
    """
    if not date_str:
        return datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Try different date formats
    formats = [
        "%d.%m.%Y",  # 31.12.2023
        "%d/%m/%Y",  # 31/12/2023
        "%Y-%m-%d",  # 2023-12-31
        "%d.%m.%y",  # 31.12.23
        "%d/%m/%y",  # 31/12/23
        "%B %d, %Y",  # December 31, 2023
        "%d %B %Y",   # 31 December 2023
    ]
    
    for fmt in formats:
        try:
            # Parse the date
            parsed_date = datetime.datetime.strptime(date_str, fmt)
            # Return in standard format
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all formats fail, try to extract date with regex
    # Look for patterns like DD.MM.YYYY or DD/MM/YYYY
    date_regex = r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})"
    match = re.search(date_regex, date_str)
    if match:
        day, month, year = match.groups()
        
        # Handle 2-digit years
        if len(year) == 2:
            # Assume 20xx for years less than 50, 19xx otherwise
            year = f"20{year}" if int(year) < 50 else f"19{year}"
        
        try:
            # Create date object
            parsed_date = datetime.datetime(int(year), int(month), int(day))
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    # If all else fails, return today's date
    logger.warning("Could not parse date: {}, using today's date".format(date_str))
    return datetime.datetime.now().strftime("%Y-%m-%d")

def clean_vendor_name(vendor_name: str) -> str:
    """
    Clean and normalize vendor name
    
    Args:
        vendor_name: Raw vendor name
        
    Returns:
        str: Cleaned vendor name
    """
    if not vendor_name:
        return "Unknown Vendor"
    
    # Remove multiple spaces
    vendor_name = re.sub(r"\s+", " ", vendor_name.strip())
    
    # Remove common prefixes like "ООО", "ИП", etc.
    vendor_name = re.sub(r"^(ООО|ИП|АО|ЗАО|ОАО)\s+", "", vendor_name)
    
    # Remove quotes
    vendor_name = vendor_name.replace('"', '').replace("'", "")
    
    return vendor_name.strip()

def normalize_amount(amount) -> float:
    """
    Normalize amount to float
    
    Args:
        amount: Amount in various formats
        
    Returns:
        float: Normalized amount
    """
    if isinstance(amount, (int, float)):
        return float(amount)
    
    if not amount:
        return 0.0
    
    # If it's a string, clean it
    if isinstance(amount, str):
        # Remove currency symbols, spaces, etc.
        amount = re.sub(r"[^\d.,]", "", amount)
        
        # Replace comma with dot for decimal point
        amount = amount.replace(",", ".")
        
        # Handle multiple dots (e.g. 1.234.56 → 1234.56)
        if amount.count(".") > 1:
            # Keep last dot as decimal point, remove others
            parts = amount.split(".")
            decimal_part = parts.pop()
            whole_part = "".join(parts)
            amount = f"{whole_part}.{decimal_part}"
    
    try:
        return float(amount)
    except (ValueError, TypeError):
        logger.warning("Could not convert amount to float: {}".format(amount))
        return 0.0

def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an invoice item
    
    Args:
        item: Raw item data
        
    Returns:
        dict: Processed item data
    """
    # Skip empty items
    if not item or not item.get("name"):
        return None
    
    # Initialize processed item
    processed_item = {
        "name": item.get("name", "").strip(),
        "quantity": normalize_amount(item.get("quantity", 1)),
        "price": normalize_amount(item.get("price", 0))
    }
    
    # Ensure minimum quantity is 1
    if processed_item["quantity"] <= 0:
        processed_item["quantity"] = 1
    
    # Try to match with product database
    product_id = get_product_id_from_mapping(processed_item["name"])
    
    if product_id:
        # We have a learned mapping
        product = get_product_by_id(product_id)
        if product:
            processed_item["product_id"] = product_id
            processed_item["product_name"] = product.get("name")
    else:
        # Try fuzzy matching
        product_id, score = match(processed_item["name"])
        if product_id and score > 0.7:
            product = get_product_by_id(product_id)
            if product:
                processed_item["product_id"] = product_id
                processed_item["product_name"] = product.get("name")
                processed_item["match_score"] = score
    
    return processed_item

def format_invoice_for_display(invoice_data: Dict[str, Any]) -> str:
    """
    Format invoice data for display in Telegram message
    
    Args:
        invoice_data: Processed invoice data
        
    Returns:
        str: Formatted invoice data for display
    """
    # Format date
    try:
        date_obj = datetime.datetime.strptime(invoice_data.get("date", ""), "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")
    except ValueError:
        formatted_date = invoice_data.get("date", "Дата не указана")
    
    # Format vendor and total
    vendor_name = invoice_data.get("vendor_name", "Не указан")
    total_amount = invoice_data.get("total_amount", 0)
    
    # Start building the message
    message = (
        "📄 <b>Данные накладной</b>\n\n"
        f"<b>Поставщик:</b> {vendor_name}\n"
        f"<b>Дата:</b> {formatted_date}\n"
        f"<b>Сумма:</b> {total_amount:.2f} руб.\n\n"
        "<b>Товары:</b>\n"
    )
    
    # Add items
    for i, item in enumerate(invoice_data.get("items", []), 1):
        name = item.get("name", "Без названия")
        quantity = item.get("quantity", 0)
        price = item.get("price", 0)
        total = quantity * price
        
        # Check if matched with product
        if "product_name" in item:
            name = f"{name} → <i>{item['product_name']}</i>"
        
        # Add item line
        message += f"{i}. {name}\n   {quantity} × {price:.2f} = {total:.2f} руб.\n"
    
    return message
