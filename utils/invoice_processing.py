"""
Module for processing invoice data.

Contains functions for formatting, matching items, and enriching invoice data.
"""
import dataclasses
import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from utils.learning import load_unit_conversions
from utils.match import is_valid_unit, match_supplier_buyer

# Get logger
logger = logging.getLogger(__name__)

__all__ = [
    "apply_unit_conversions",
    "format_invoice_data",
    "format_final_invoice",
    "match_invoice_items",
    "enrich_invoice",
    "format_invoice_for_display",
    "check_product_exists",
    "extract_supplier_buyer",
    "ensure_result",
    "validate_item",
]


def format_currency(value: float, include_decimals: bool = False) -> str:
    """
    Format currency value in Indonesian Rupiah (IDR)
    
    Args:
        value: The amount to format
        include_decimals: Whether to include decimal places
    
    Returns:
        str: Formatted currency string
    """
    if include_decimals:
        return f"IDR {value:,.2f}"
    else:
        # Only show decimals if they're not zero
        if value == int(value):
            return f"IDR {int(value):,}"
        else:
            return f"IDR {value:,.2f}"


def validate_item(item: Dict) -> Dict:
    """
    Validate an invoice item's units and quantities
    
    Args:
        item: Invoice item to validate
    
    Returns:
        dict: Validated item with match_status updated
    """
    # Create a copy to avoid modifying the original
    validated = item.copy()
    
    # Check if unit is valid
    unit = item.get("unit", "")
    if unit and not is_valid_unit(unit):
        validated["match_status"] = "unmatched"
        validated["validation_error"] = "invalid_unit"
        return validated
    
    # Check if quantity is valid
    qty = item.get("quantity", item.get("qty", 0))
    if qty <= 0:
        validated["match_status"] = "unmatched"
        validated["validation_error"] = "invalid_quantity"
        return validated
    
    # If item was already unmatched, keep it that way
    if item.get("match_status") == "unmatched":
        validated["match_status"] = "unmatched"
        
    return validated


def apply_unit_conversions(matched_data: Dict) -> List[Dict]:
    """
    Apply unit conversions to invoice items.

    Args:
        matched_data: Invoice data with matched products

    Returns:
        list: List of applied conversions
    """
    # Load conversion data
    unit_conversions = load_unit_conversions()
    
    # List to store information about applied conversions
    conversions_applied = []
    
    # Process items in the invoice
    for i, line in enumerate(matched_data.get("lines", [])):
        product_id = line.get("product_id")
        product_name = line.get("name", "")
        source_unit = line.get("unit", "")
        
        # Skip if no product ID or unit of measure
        if not product_id or not source_unit:
            continue
            
        # Check if there's a conversion for this unit
        if source_unit in unit_conversions:
            conversions = unit_conversions[source_unit]
            
            # Choose the first suitable conversion
            # In a real scenario, there might be more complex selection logic
            for target_unit, factor in conversions.items():
                # Apply conversion
                original_qty = line.get("qty", 0)
                line["original_qty"] = original_qty
                line["original_unit"] = source_unit
                line["qty"] = original_qty * factor
                line["unit"] = target_unit
                line["conversion_applied"] = True
                
                # Save conversion information
                conversions_applied.append({
                    "line_index": i,
                    "product_name": product_name,
                    "product_id": product_id,
                    "original_qty": original_qty,
                    "original_unit": source_unit,
                    "converted_qty": original_qty * factor,
                    "converted_unit": target_unit,
                    "conversion_factor": factor,
                })
                
                # Use only the first conversion
                break
    
    logger.info("Applied %d unit conversions", len(conversions_applied))
    return conversions_applied


def format_invoice_data(user_data: Dict) -> str:
    """
    Format invoice data for display to the user.

    Args:
        user_data: User data with invoice information

    Returns:
        str: Formatted text with invoice data
    """
    matched_data = user_data.get("matched_data", {})
    
    # Format header
    supplier = matched_data.get("supplier", "Unknown supplier")
    total = matched_data.get("total", 0)
    
    message = "📄 *Invoice from {}*\n\n".format(supplier)
    
    # Add information about products
    message += "*Products:*\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown product")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        product_id = line.get("product_id")
        match_score = line.get("match_score", 0)
        
        # Format product line
        item_price = qty * price
        item_line = "{}. {} - {} {} × {} = {}".format(
            line_num, name, qty, unit, format_currency(price), format_currency(item_price)
        )
        
        # Add matching information
        if product_id:
            status = "✅" if match_score > 0.8 else "⚠️"
            item_line += " {}".format(status)
        else:
            item_line += " ❓"
            
        message += item_line + "\n"
    
    # Add information about conversions
    conversions = user_data.get("conversions_applied", [])
    if conversions:
        message += "\n*Applied conversions:*\n"
        for conv in conversions:
            message += "• {}: {} {} → {} {}\n".format(
                conv['product_name'],
                conv['original_qty'],
                conv['original_unit'],
                conv['converted_qty'],
                conv['converted_unit']
            )
    
    # Add total
    message += "\n*Total:* {}".format(format_currency(total))
    
    return message


def format_final_invoice(user_data: Dict) -> str:
    """
    Format final invoice data for confirmation before sending.

    Args:
        user_data: User data with invoice information

    Returns:
        str: Formatted text with final invoice data
    """
    matched_data = user_data.get("matched_data", {})
    
    # Format header
    supplier = matched_data.get("supplier", "Unknown supplier")
    total = matched_data.get("total", 0)
    
    message = "📋 *FINAL INVOICE*\n\n"
    message += "*Supplier:* {}\n\n".format(supplier)
    
    # Add products table
    message += "*PRODUCTS:*\n"
    message += "```\n"
    message += "# Name                           Qty        Price      Total     \n"
    message += "-" * 70 + "\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown product")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        
        # Trim long names
        display_name = name[:27] + "..." if len(name) > 30 else name
        
        # Format table row
        item_price = qty * price
        line_str = "{:<3} {:<30} {} {:<6} {:<10} {:<10}\n".format(
            line_num, display_name, qty, unit, format_currency(price), format_currency(item_price)
        )
        message += line_str
    
    message += "-" * 70 + "\n"
    message += "TOTAL:                                            {}\n".format(format_currency(total))
    message += "```\n\n"
    
    # Add actions information
    message += "*Actions:*\n"
    message += "• Confirm and send to Syrve\n"
    message += "• Return to editing\n"
    message += "• Cancel and start over\n"
    
    return message


async def match_invoice_items(invoice_data) -> Dict:
    """
    Match invoice products with the database.

    Args:
        invoice_data: Invoice data from OCR

    Returns:
        dict: Invoice with matched products
    """
    from utils.match import match
    
    # Create a copy of the data to avoid modifying the original
    matched_data: Dict[str, Any] = dataclasses.asdict(invoice_data)
    
    # Convert products to string format for matching
    lines = []
    for item in invoice_data.items:
        # Create basic line structure
        line = {
            "name": item.get("name", ""),
            "qty": item.get("qty", 0),
            "unit": item.get("unit", ""),
            "price": item.get("price", 0),
            "product_id": None,
            "match_score": 0,
        }
        
        # Try to match product
        product_id, score = match(line["name"])
        
        if product_id and score > 0:
            line["product_id"] = product_id
            line["match_score"] = score
            logger.info("Matched item: %s -> %s (score: %.2f)", line["name"], product_id, score)
        else:
            logger.info("No match found for item: %s", line["name"])
        
        lines.append(line)
    
    # Replace product list with matched ones
    matched_data["lines"] = lines
    
    return matched_data


async def extract_supplier_buyer(parsed_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and match supplier and buyer information from OCR results
    
    Args:
        parsed_invoice: Dictionary with invoice data after OCR
    
    Returns:
        Dict[str, Any]: Matched supplier and buyer information
    """
    # Extract supplier and buyer names from the invoice
    vendor_name = parsed_invoice.get("vendor_name", "")
    buyer_name = parsed_invoice.get("buyer_name", "")
    
    # Match against the database
    match_result = await match_supplier_buyer(vendor_name, buyer_name)
    
    # Return the result
    return match_result


async def enrich_invoice(parsed_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich invoice data by matching with product database
    and adding additional information.
    
    Args:
        parsed_invoice: Dictionary with invoice data after OCR
    
    Returns:
        Dict[str, Any]: Enriched invoice data
    """
    from utils.match import match_products
    
    # Create a copy of original data
    enriched = parsed_invoice.copy()
    
    # Match supplier and buyer
    supplier_buyer_info = await extract_supplier_buyer(parsed_invoice)
    enriched.update(supplier_buyer_info)
    
    # Get list of items for matching
    items = parsed_invoice.get("items", [])
    
    # Match items with database
    enriched_items = await match_products(items)
    
    # Validate each item (units, quantities)
    validated_items = [validate_item(item) for item in enriched_items]
    
    # Replace item list with enriched and validated ones
    enriched["items"] = validated_items
    
    # Calculate statistics
    matched_count = sum(1 for item in validated_items if item.get("match_status") == "matched")
    unmatched_count = len(validated_items) - matched_count
    
    # Calculate total quantities and amounts
    total_qty_matched = sum(
        item.get("quantity", 0) 
        for item in validated_items 
        if item.get("match_status") == "matched"
    )
    
    total_sum_matched_idr = sum(
        item.get("quantity", 0) * item.get("price", 0)
        for item in validated_items
        if item.get("match_status") == "matched"
    )
    
    # Add statistics to enriched data
    enriched["matched_count"] = matched_count
    enriched["unmatched_count"] = unmatched_count
    enriched["total_qty_matched"] = total_qty_matched
    enriched["total_sum_matched_idr"] = total_sum_matched_idr
    enriched["total_items"] = len(validated_items)
    
    # Add metadata
    enriched["enriched_at"] = datetime.datetime.now().isoformat()
    
    return enriched


async def ensure_result(result_dict: Dict) -> Dict:
    """
    Ensure the invoice processing result is complete and valid
    
    Args:
        result_dict: Result dictionary from processing
    
    Returns:
        Dict: Validated and completed result
    """
    # Ensure we have a valid dictionary
    if not isinstance(result_dict, dict):
        logger.error("Invalid result type: %s", type(result_dict))
        return {}
    
    # Ensure basic fields exist
    result = result_dict.copy()
    if "items" not in result:
        result["items"] = []
    
    if "total_amount" not in result:
        # Calculate total if not provided
        result["total_amount"] = sum(
            item.get("quantity", 0) * item.get("price", 0)
            for item in result.get("items", [])
        )
    
    # Ensure vendor and buyer information
    if "vendor_name" not in result:
        result["vendor_name"] = "Unknown Supplier"
    
    if "buyer_name" not in result:
        result["buyer_name"] = "Unknown Buyer"
    
    # Ensure date field
    if "date" not in result:
        result["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    
    return result


def format_invoice_for_display(invoice_dict: Dict) -> str:
    """
    Convert the result of match_invoice_items (dictionary) to readable
    text for Telegram: header, table of lines, total.

    Args:
        invoice_dict: Invoice data dictionary

    Returns:
        str: Formatted string for display
    """
    # Extract basic data
    vendor_name = invoice_dict.get("vendor_name", "Unknown Supplier")
    vendor_id = invoice_dict.get("vendor_id")
    buyer_name = invoice_dict.get("buyer_name", "Restaurant X")
    buyer_id = invoice_dict.get("buyer_id")
    date = invoice_dict.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
    total_amount = invoice_dict.get("total_amount", 0)
    items = invoice_dict.get("items", [])
    
    # Count matched and unmatched items
    matched_items = [item for item in items if item.get("match_status") == "matched"]
    unmatched_items = [item for item in items if item.get("match_status") != "matched"]
    matched_count = len(matched_items)
    unmatched_count = len(unmatched_items)
    
    # Calculate total matched amount
    total_matched = sum(
        item.get("quantity", item.get("qty", 0)) * item.get("price", 0)
        for item in matched_items
    )
    
    # Format date (if provided as string in YYYY-MM-DD format)
    try:
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d %b %Y")
    except (ValueError, TypeError):
        formatted_date = date
    
    # Format header
    result = [
        "📄 <b>Invoice</b>",
        f"Supplier : {vendor_name}" + (f" (ID {vendor_id}) ✓" if vendor_id else " ⚠️"),
        f"Buyer    : {buyer_name}" + (f" (ID {buyer_id}) ✓" if buyer_id else " ⚠️"),
        f"Scanned  : {formatted_date}",
        ""
    ]
    
    # Add match statistics
    if matched_count > 0:
        result.append(f"✔ Matched {matched_count} / {len(items)} lines — {format_currency(total_matched)}")
    if unmatched_count > 0:
        result.append(f"✖ Need fix {unmatched_count}")
    
    result.append("")
    
    # Add matched items section
    if matched_items:
        result.append("--- MATCHED ({}) ---".format(matched_count))
        
        for i, item in enumerate(matched_items, 1):
            name = item.get("name", "")
            quantity = item.get("quantity", item.get("qty", 0))
            unit = item.get("unit", "")
            price = item.get("price", 0)
            total_item = quantity * price
            
            # Format dots for alignment
            dots = "." * (20 - len(name)) if len(name) < 20 else "..."
            
            # Format product line
            item_line = f"{i}. {name}{dots} {quantity} {unit} × {format_currency(price)} = {format_currency(total_item)}"
            result.append(item_line)
        
        result.append("")
    
    # Add unmatched items section
    if unmatched_items:
        result.append("--- NEED FIX ({}) ---".format(unmatched_count))
        
        for i, item in enumerate(unmatched_items, matched_count + 1):
            name = item.get("name", "")
            quantity = item.get("quantity", item.get("qty", 0))
            unit = item.get("unit", "")
            price = item.get("price", 0)
            total_item = quantity * price
            
            # Format dots for alignment
            dots = "." * (20 - len(name)) if len(name) < 20 else "..."
            
            # Format product line
            item_line = f"{i}. {name}{dots} {quantity} {unit} × {format_currency(price)} = {format_currency(total_item)}  [✏️ Fix_{i}]"
            result.append(item_line)
    
    # Add total
    result.append("")
    result.append(f"<b>Total:</b> {format_currency(total_amount)}")
    
    return "\n".join(result)


async def check_product_exists(product_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a product exists in the database.

    Args:
        product_name: Product name

    Returns:
        tuple: (whether the product exists, product ID if it exists)
    """
    from utils.match import match
    
    # Try to find product in database
    product_id, score = match(product_name)
    
    if product_id and score > 0.9:
        logger.info("Product exists: %s -> %s (score: %.2f)", product_name, product_id, score)
        return True, product_id
    
    # If product not found, return False and None
    logger.info("Product does not exist: %s", product_name)
    return False, None
