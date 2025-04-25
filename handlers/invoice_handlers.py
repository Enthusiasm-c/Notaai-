"""
Handlers for working with invoices in the Telegram bot.

This module contains functions for processing invoice photos and their confirmation callbacks.
"""

import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO, FIX_ITEM
from services.ocr_service import extract
from services.syrve_service import commit_document
from utils.configuration import Config
from utils.error_handling import log_error, save_error_image
from utils.invoice_processing import enrich_invoice, format_invoice_for_display, ensure_result
from utils.storage import save_temp_file

__all__ = ["handle_invoice", "handle_invoice_callback", "handle_fix_item_callback"]

# Logging setup
logger = logging.getLogger(__name__)


async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for receiving invoice photos.
    
    Args:
        update: Telegram Update object
        context: Bot context
        
    Returns:
        int: Next dialog state
    """
    try:
        user = update.effective_user
        logger.info(f"Received invoice photo from user {user.id} ({user.username})")
        
        # Send processing message
        processing_message = await update.message.reply_text(
            "⏳ Processing document... This may take up to 30 seconds."
        )
        
        # Get file ID
        file_id = None
        file_type = None
        
        if update.message.photo:
            # Take the last (largest) photo
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        elif update.message.document and update.message.document.mime_type == "application/pdf":
            file_id = update.message.document.file_id
            file_type = "document"
        else:
            await update.message.reply_text(
                "❌ Please send an invoice photo or PDF document."
            )
            return WAIT_PHOTO
        
        # Download file
        file = await context.bot.get_file(file_id)
        
        # Create temp directory if it doesn't exist
        temp_dir = Path("/tmp") / "notaai"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=".jpg") as temp_file:
            temp_path = temp_file.name
            await file.download_to_drive(temp_path)
        
        # Process image with OCR
        config = Config()
        
        # Extract invoice data
        invoice_data = await extract(temp_path)
        
        # Log OCR result
        logger.info(f"OCR result: {json.dumps(asdict(invoice_data), ensure_ascii=False)[:500]}...")
        
        # Match invoice items with database
        raw = await enrich_invoice(asdict(invoice_data))
        invoice_data = await ensure_result(raw)
        
        # Format invoice data for display
        formatted_message = format_invoice_for_display(invoice_data)
        
        # Create keyboard with action buttons
        keyboard = []
        
        # Check if supplier and buyer are set
        supplier_id = invoice_data.get("vendor_id")
        buyer_found = invoice_data.get("buyer_found", False)
        
        # Add supplier selection button if needed
        if not supplier_id:
            keyboard.append([
                InlineKeyboardButton("🖊️ Select supplier", callback_data="select_supplier")
            ])
        
        # Add buyer input button if needed
        if not buyer_found:
            keyboard.append([
                InlineKeyboardButton("🖊️ Set buyer", callback_data="set_buyer")
            ])
        
        # Add fix buttons for unmatched or invalid items
        unmatched_items = [
            item for item in invoice_data.get("items", [])
            if item.get("match_status") == "unmatched" or not item.get("is_valid", True)
        ]
        
        fix_buttons = []
        for i, item in enumerate(unmatched_items):
            item_index = invoice_data["items"].index(item)
            fix_buttons.append(
                InlineKeyboardButton(f"Fix_{item_index+1}", callback_data=f"fix_item_{item_index}")
            )
            
            # Create rows with 3 buttons each
            if len(fix_buttons) == 3 or i == len(unmatched_items) - 1:
                keyboard.append(fix_buttons)
                fix_buttons = []
        
        # Add confirm button only if all items are matched and valid, and supplier/buyer are set
        unmatched_count = invoice_data.get("unmatched_count", 0)
        if unmatched_count == 0 and supplier_id and buyer_found:
            keyboard.append([
                InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve"),
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Save invoice data in user context
        context.user_data["invoice"] = invoice_data
        
        # Save image to temporary storage
        with open(temp_path, "rb") as f:
            image_data = f.read()
        
        file_key = save_temp_file(user.id, image_data)
        context.user_data["invoice_image_key"] = file_key
        
        # Edit processing message
        await processing_message.edit_text(
            formatted_message + "\n\n<i>Review the data and fix any issues.</i>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        
        return CONFIRMATION
    
    except Exception as e:
        # Log error
        log_error(f"Error processing invoice: {str(e)}", e)
        
        # Save error-causing image if available
        if update.message.photo and "image_data" in locals():
            save_error_image(user.id, image_data)
        
        # Notify user
        await update.message.reply_text(
            "❌ An error occurred while processing the document. Please try again or contact support."
        )
        
        return WAIT_PHOTO


async def handle_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for callbacks to confirm/reject invoice.
    
    Args:
        update: Telegram Update object
        context: Bot context
        
    Returns:
        int: Next dialog state
    """
    query = update.callback_query
    user = query.from_user
    
    # Answer callback to remove loading indicator
    await query.answer()
    
    # Get callback data
    callback_data = query.data
    
    if callback_data == "send_to_syrve":
        invoice_data = context.user_data.get("invoice", {})
        
        # Call Syrve service to commit document
        success = await commit_document(invoice_data)
        
        if success:
            await query.edit_message_text(
                "Invoice sent to Syrve ✔️",
                parse_mode="HTML",
            )
            
            logger.info(f"User {user.id} sent invoice to Syrve")
        else:
            # If sending failed
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Retry", callback_data="send_to_syrve"),
                    InlineKeyboardButton("❌ Cancel", callback_data="reject_invoice"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                query.message.text + "\n\n❌ <b>Failed to send to Syrve. Please try again.</b>",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            
            logger.error(f"User {user.id} failed to send invoice to Syrve")
            return CONFIRMATION
        
        return WAIT_PHOTO
    
    elif callback_data == "back_to_edit":
        # Return to editing invoice
        invoice_data = context.user_data.get("invoice", {})
        formatted_message = format_invoice_for_display(invoice_data)
        
        # Create keyboard with action buttons
        keyboard = []
        
        # Check if supplier and buyer are set
        supplier_id = invoice_data.get("vendor_id")
        buyer_found = invoice_data.get("buyer_found", False)
        
        # Add supplier selection button if needed
        if not supplier_id:
            keyboard.append([
                InlineKeyboardButton("🖊️ Select supplier", callback_data="select_supplier")
            ])
        
        # Add buyer input button if needed
        if not buyer_found:
            keyboard.append([
                InlineKeyboardButton("🖊️ Set buyer", callback_data="set_buyer")
            ])
        
        # Add fix buttons for unmatched items
        unmatched_items = [
            item for item in invoice_data.get("items", [])
            if item.get("match_status") == "unmatched" or not item.get("is_valid", True)
        ]
        
        fix_buttons = []
        for i, item in enumerate(unmatched_items):
            item_index = invoice_data["items"].index(item)
            fix_buttons.append(
                InlineKeyboardButton(f"Fix_{item_index+1}", callback_data=f"fix_item_{item_index}")
            )
            
            # Create rows with 3 buttons each
            if len(fix_buttons) == 3 or i == len(unmatched_items) - 1:
                keyboard.append(fix_buttons)
                fix_buttons = []
        
        # Add confirm button if all items are valid and supplier/buyer are set
        unmatched_count = invoice_data.get("unmatched_count", 0)
        if unmatched_count == 0 and supplier_id and buyer_found:
            keyboard.append([
                InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve"),
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            formatted_message + "\n\n<i>Review the data and fix any issues.</i>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        
        return CONFIRMATION
    
    elif callback_data == "reject_invoice":
        await query.edit_message_text(
            query.message.text + "\n\n❌ <b>Rejected by user.</b>",
            parse_mode="HTML",
        )
        
        logger.info(f"User {user.id} rejected invoice upload")
        
        return WAIT_PHOTO
    
    elif callback_data.startswith("fix_item_"):
        # Extract item index from callback data
        item_index = int(callback_data.split("_")[-1])
        
        # Store item index in user data
        context.user_data["fixing_item_index"] = item_index
        
        # Get invoice data
        invoice_data = context.user_data.get("invoice", {})
        items = invoice_data.get("items", [])
        
        if 0 <= item_index < len(items):
            item = items[item_index]
            
            # Ask user to enter corrected information
            await query.edit_message_text(
                f"<b>Fixing item #{item_index+1}:</b>\n\n"
                f"Current: {item.get('name', 'Unknown')} - "
                f"{item.get('quantity', 0)} {item.get('unit', 'pcs')} × "
                f"{item.get('price', 0):,.0f}\n\n"
                f"<i>Send corrected line in format:</i>\n"
                f"<code>qty unit name price</code>\n\n"
                f"Example: <code>2 kg Tomato 20000</code>",
                parse_mode="HTML",
            )
            
            return FIX_ITEM
        else:
            logger.warning(f"Invalid item index: {item_index}")
            return CONFIRMATION
    
    else:
        logger.warning(f"Unknown callback data: {callback_data}")
        return CONFIRMATION


async def handle_fix_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for fixing invoice items.
    
    Args:
        update: Telegram Update object
        context: Bot context
        
    Returns:
        int: Next dialog state
    """
    try:
        item_index = context.user_data.get("fixing_item_index")
        
        if item_index is None:
            await update.message.reply_text(
                "❌ Error: No item selected for fixing. Please try again."
            )
            return WAIT_PHOTO
        
        # Get invoice data
        invoice_data = context.user_data.get("invoice", {})
        items = invoice_data.get("items", [])
        
        if 0 <= item_index < len(items):
            # Parse user message
            text = update.message.text.strip()
            parts = text.split()
            
            if len(parts) < 4:
                await update.message.reply_text(
                    "❌ Invalid format. Please use: qty unit name price\n"
                    "Example: 2 kg Tomato 20000"
                )
                return FIX_ITEM
            
            # Extract price (last part)
            try:
                price = float(parts[-1])
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid price. Please enter a number for price."
                )
                return FIX_ITEM
            
            # Extract unit (second part)
            unit = parts[1]
            
            # Extract quantity (first part)
            try:
                quantity = float(parts[0])
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid quantity. Please enter a number for quantity."
                )
                return FIX_ITEM
            
            # Extract name (all remaining parts in the middle)
            name = " ".join(parts[2:-1])
            
            # Update item
            items[item_index].update({
                "name": name,
                "quantity": quantity,
                "unit": unit,
                "price": price,
                "match_status": "matched",  # Mark as manually matched
                "is_valid": quantity > 0 and price > 0,  # Check validity
            })
            
            # Re-validate and update item
            from utils.match import match
            product_id, score = match(name)
            
            if score >= 0.6 and product_id:
                items[item_index]["product_id"] = product_id
                items[item_index]["match_score"] = score
            
            # Update counts
            matched_count = sum(1 for item in items 
                                if item.get("match_status") == "matched" and item.get("is_valid", True))
            unmatched_count = len(items) - matched_count
            
            # Update total sums
            total_qty_matched = sum(
                item.get("quantity", 0) for item in items
                if item.get("match_status") == "matched" and item.get("is_valid", True)
            )
            total_sum_matched_idr = sum(
                item.get("quantity", 0) * item.get("price", 0)
                for item in items if item.get("match_status") == "matched" and item.get("is_valid", True)
            )
            
            # Update invoice data
            invoice_data.update({
                "items": items,
                "matched_count": matched_count,
                "unmatched_count": unmatched_count,
                "total_qty_matched": total_qty_matched,
                "total_sum_matched_idr": total_sum_matched_idr,
            })
            
            # Format updated invoice
            formatted_message = format_invoice_for_display(invoice_data)
            
            # Create keyboard with action buttons
            keyboard = []
            
            # Check if supplier and buyer are set
            supplier_id = invoice_data.get("vendor_id")
            buyer_found = invoice_data.get("buyer_found", False)
            
            # Add supplier selection button if needed
            if not supplier_id:
                keyboard.append([
                    InlineKeyboardButton("🖊️ Select supplier", callback_data="select_supplier")
                ])
            
            # Add buyer input button if needed
            if not buyer_found:
                keyboard.append([
                    InlineKeyboardButton("🖊️ Set buyer", callback_data="set_buyer")
                ])
            
            # Add fix buttons for unmatched or invalid items
            unmatched_items = [
                item for item in items
                if item.get("match_status") == "unmatched" or not item.get("is_valid", True)
            ]
            
            fix_buttons = []
            for i, item in enumerate(unmatched_items):
                item_index = items.index(item)
                fix_buttons.append(
                    InlineKeyboardButton(f"Fix_{item_index+1}", callback_data=f"fix_item_{item_index}")
                )
                
                # Create rows with 3 buttons each
                if len(fix_buttons) == 3 or i == len(unmatched_items) - 1:
                    keyboard.append(fix_buttons)
                    fix_buttons = []
            
            # Add confirm button if all items are matched and valid, and supplier/buyer are set
            if unmatched_count == 0 and supplier_id and buyer_found:
                keyboard.append([
                    InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve"),
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send updated invoice to user
            await update.message.reply_text(
                formatted_message + "\n\n<i>Item updated. Review and confirm when ready.</i>",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            
            # Update user data
            context.user_data["invoice"] = invoice_data
            
            return CONFIRMATION
        else:
            logger.warning(f"Invalid item index: {item_index}")
            await update.message.reply_text(
                "❌ Error: Invalid item index. Please try again."
            )
            return WAIT_PHOTO
    
    except Exception as e:
        log_error(f"Error fixing invoice item: {str(e)}", e)
        
        await update.message.reply_text(
            "❌ An error occurred while updating the item. Please try again."
        )
        
        return WAIT_PHOTO
