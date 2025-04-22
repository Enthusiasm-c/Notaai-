import logging
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.match import match, get_product_by_id, save_product
from utils.learning import save_learned_mapping, get_product_id_from_mapping

# Set up logging
logger = logging.getLogger(__name__)

async def handle_item_matching(update: Update, context: ContextTypes.DEFAULT_TYPE, item: dict) -> dict:
    """
    Handle item matching for items in an invoice
    
    Args:
        update: Update object
        context: Context object
        item: Item data
        
    Returns:
        dict: Updated item data with matched product
    """
    item_name = item.get("name", "").strip()
    if not item_name:
        logger.warning("Empty item name, skipping matching")
        return item
    
    # Check if we already have this mapping in learning database
    product_id = get_product_id_from_mapping(item_name)
    
    if product_id:
        # We have a learned mapping
        logger.info(f"Using learned mapping for '{item_name}': {product_id}")
        
        # Get product details
        product = get_product_by_id(product_id)
        if product:
            # Update item with product info
            item["product_id"] = product_id
            item["product_name"] = product.get("name")
            item["category"] = product.get("category")
            return item
    
    # No learned mapping, try fuzzy matching
    product_id, score = match(item_name)
    
    if product_id:
        # We have a fuzzy match
        logger.info(f"Fuzzy match for '{item_name}': {product_id} (score: {score:.2f})")
        
        # Get product details
        product = get_product_by_id(product_id)
        if product:
            # Update item with product info
            item["product_id"] = product_id
            item["product_name"] = product.get("name")
            item["category"] = product.get("category")
            item["match_score"] = score
            
            # If match is very good (score > 0.9), save as learned mapping
            if score > 0.9:
                save_learned_mapping(item_name, product_id)
                logger.info(f"Automatically saved mapping for '{item_name}': {product_id} (score: {score:.2f})")
            
            return item
    
    # No match found, need user interaction
    logger.info(f"No match found for '{item_name}', will ask user")
    
    # This would normally trigger an interactive selection process
    # For now, we'll just mark it as unmatched
    item["product_id"] = None
    item["match_required"] = True
    
    return item

async def handle_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    """
    Handle item selection from inline keyboard
    
    Args:
        update: Update object
        context: Context object
        data: Callback data
    """
    query = update.callback_query
    item_name = data.get("item_name")
    product_id = data.get("product_id")
    
    if not item_name or not product_id:
        logger.warning("Missing item_name or product_id in callback data")
        await query.answer("Ошибка: неполные данные")
        return
    
    try:
        # Get product details
        product = get_product_by_id(product_id)
        
        if not product:
            logger.warning(f"Product not found: {product_id}")
            await query.answer("Товар не найден в базе данных")
            return
        
        # Save mapping for future use
        save_learned_mapping(item_name, product_id)
        
        # Update message
        await query.edit_message_text(
            f"Сопоставление сохранено:\n\n"
            f"<b>{item_name}</b>\n"
            f"↓\n"
            f"<b>{product.get('name')}</b> (ID: {product_id})",
            parse_mode="HTML"
        )
        
        logger.info(f"User selected product '{product.get('name')}' for item '{item_name}'")
        
        # Answer callback query
        await query.answer("Сопоставление сохранено")
        
    except Exception as e:
        logger.error(f"Error handling item selection: {str(e)}", exc_info=True)
        await query.answer("Произошла ошибка при сохранении сопоставления")

async def send_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, item_name: str, candidates: list) -> None:
    """
    Send item selection message with buttons
    
    Args:
        update: Update object
        context: Context object
        item_name: Item name from invoice
        candidates: List of candidate products
    """
    # Create message
    message = f"Пожалуйста, выберите товар для:\n\n<b>{item_name}</b>\n\nВарианты:"
    
    # Create keyboard with product options
    keyboard = []
    
    # Add top 5 candidates
    for product in candidates[:5]:
        product_id = product.get("id")
        product_name = product.get("name")
        score = product.get("score", 0)
        
        # Create button with callback data
        callback_data = json.dumps({
            "action": "select_item",
            "item_name": item_name,
            "product_id": product_id
        })
        
        # Add button to keyboard
        keyboard.append([
            InlineKeyboardButton(
                f"{product_name} ({score:.2f})",
                callback_data=callback_data
            )
        ])
    
    # Add "Not in list" option
    callback_data = json.dumps({
        "action": "not_in_list",
        "item_name": item_name
    })
    keyboard.append([InlineKeyboardButton("Нет в списке / Добавить новый", callback_data=callback_data)])
    
    # Send message with keyboard
    await update.effective_chat.send_message(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    logger.info(f"Sent item selection message for '{item_name}' with {len(candidates)} candidates")

async def handle_new_product(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    """
    Handle adding a new product
    
    Args:
        update: Update object
        context: Context object
        data: Callback data
    """
    query = update.callback_query
    item_name = data.get("item_name")
    
    if not item_name:
        logger.warning("Missing item_name in callback data")
        await query.answer("Ошибка: неполные данные")
        return
    
    # Start conversation for adding new product
    context.user_data["adding_product"] = {
        "item_name": item_name,
        "step": "request_id"
    }
    
    # Answer callback query
    await query.answer()
    
    # Edit message to request product ID
    await query.edit_message_text(
        f"Добавление нового товара для:\n\n"
        f"<b>{item_name}</b>\n\n"
        "Пожалуйста, введите ID товара в Syrve:",
        parse_mode="HTML"
    )
    
    logger.info(f"Started new product addition for '{item_name}'")

async def handle_product_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product ID input
    
    Args:
        update: Update object
        context: Context object
    """
    # Check if we're in the product adding flow
    if "adding_product" not in context.user_data:
        return
    
    # Get product data and input
    product_data = context.user_data["adding_product"]
    if product_data.get("step") != "request_id":
        return
    
    # Get input text
    product_id = update.message.text.strip()
    
    # Update product data
    product_data["product_id"] = product_id
    product_data["step"] = "request_name"
    
    # Ask for product name
    await update.effective_chat.send_message(
        f"ID товара: <b>{product_id}</b>\n\n"
        "Теперь введите название товара:",
        parse_mode="HTML"
    )
    
    logger.info(f"Received product ID '{product_id}' for new product")

async def handle_product_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product name input
    
    Args:
        update: Update object
        context: Context object
    """
    # Check if we're in the product adding flow
    if "adding_product" not in context.user_data:
        return
    
    # Get product data and input
    product_data = context.user_data["adding_product"]
    if product_data.get("step") != "request_name":
        return
    
    # Get input text
    product_name = update.message.text.strip()
    
    # Get other data
    product_id = product_data.get("product_id")
    item_name = product_data.get("item_name")
    
    # Save new product
    if save_product(product_id, product_name):
        # Save mapping
        save_learned_mapping(item_name, product_id)
        
        # Notify user
        await update.effective_chat.send_message(
            "✅ Товар успешно добавлен и сопоставлен!\n\n"
            f"ID: <b>{product_id}</b>\n"
            f"Название: <b>{product_name}</b>\n"
            f"Исходное название: <b>{item_name}</b>",
            parse_mode="HTML"
        )
        
        logger.info(f"Added new product '{product_name}' (ID: {product_id}) for '{item_name}'")
    else:
        # Notify user of error
        await update.effective_chat.send_message(
            "❌ Не удалось сохранить товар. Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )
        
        logger.error(f"Failed to save new product for '{item_name}'")
    
    # Clear conversation state
    context.user_data.pop("adding_product", None)
