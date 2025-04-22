import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import (
    CONFIRMATION,
    EDIT_ITEM,
    FINAL_CONFIRMATION,
    SELECT_EDIT_ITEM,
    WAIT_PHOTO,
    user_data,
)
from handlers.item_handlers import display_item_selection
from services.syrve_service import authenticate, commit_document, send_invoice_to_syrve
from utils.error_handling import log_error
from utils.invoice_processing import (
    format_final_invoice,
    format_invoice_data,
    prepare_invoice_data_for_syrve,
    save_invoice_data,
)

# Получаем логгер
logger = logging.getLogger(__name__)


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик подтверждения или редактирования результатов

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_data:
            await query.edit_message_text(text="❌ Error: Invoice data not found.")
            return WAIT_PHOTO

        # Действие: Окончательное подтверждение и отправка в Syrve
        if query.data == "confirm":
            await query.edit_message_text(text="✅ Confirmed! Saving data and sending to Syrve...")

            try:
                # Сохраняем данные в файл
                filename = save_invoice_data(user_id, user_data[user_id]["matched_data"])

                # Получаем токен для доступа к Syrve API
                logger.info(f"Authenticating with Syrve API")
                token = await authenticate()

                if not token:
                    log_error("Failed to authenticate with Syrve API")
                    await query.edit_message_text(
                        text=f"❌ Data saved, but could not authenticate with Syrve API. Check error logs for details."
                    )
                    return WAIT_PHOTO

                # Преобразуем данные в формат для отправки в Syrve
                invoice_data = prepare_invoice_data_for_syrve(user_data[user_id]["matched_data"])

                # Отправляем данные в Syrve
                logger.info(f"Sending invoice data to Syrve")
                document_id = await send_invoice_to_syrve(token, invoice_data)

                if document_id:
                    # Проводим документ в Syrve
                    logger.info(f"Invoice sent successfully, committing document {document_id}")
                    commit_success = await commit_document(token, document_id)

                    if commit_success:
                        logger.info(f"Document {document_id} committed successfully")
                        await query.edit_message_text(
                            text=f"✅ Success! Invoice sent to Syrve and committed.\n"
                            f"Document ID: {document_id}"
                        )
                    else:
                        log_error(f"Failed to commit document {document_id}")
                        await query.edit_message_text(
                            text=f"⚠️ Invoice sent to Syrve (ID: {document_id}), but could not be committed. "
                            f"Please commit it manually in Syrve."
                        )
                else:
                    log_error(f"Failed to send invoice to Syrve")
                    await query.edit_message_text(
                        text=f"❌ Data saved to {filename}, but an error occurred when sending to Syrve. "
                        f"Check error logs for details."
                    )

                # Очищаем данные пользователя
                del user_data[user_id]

            except Exception as e:
                error_msg = f"Error saving/sending data: {e}"
                log_error(error_msg, exc_info=True)
                await query.edit_message_text(
                    text=f"❌ An error occurred while saving/sending data: {str(e)}"
                )

            return WAIT_PHOTO

        # Действие: Отмена процесса
        elif query.data == "cancel_process":
            if user_id in user_data:
                del user_data[user_id]

            await query.edit_message_text(text="Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        # Действие: Редактирование неопознанных товаров
        elif query.data == "edit_unmatched":
            # Находим первый неопознанный товар
            matched_data = user_data[user_id]["matched_data"]
            unmatched_index = None

            for i, line in enumerate(matched_data.get("lines", [])):
                if line.get("product_id") is None:
                    unmatched_index = i
                    break

            if unmatched_index is not None:
                # Сохраняем индекс текущего редактируемого товара
                user_data[user_id]["current_edit_index"] = unmatched_index

                # Сохраняем текущее состояние для возможности возврата
                user_data[user_id]["edit_history"] = []

                # Отображаем информацию о товаре и варианты действий
                from handlers.item_handlers import display_item_edit_options

                await display_item_edit_options(query, user_id, unmatched_index)
                return EDIT_ITEM
            else:
                # Если все товары распознаны, переходим к подтверждению
                await query.edit_message_text(
                    text="All items are now recognized. Ready to review final invoice?",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Review Final Invoice",
                                    callback_data="final_preview",
                                )
                            ],
                            [InlineKeyboardButton("Cancel", callback_data="cancel_process")],
                        ]
                    ),
                )
                return CONFIRMATION

        # Действие: Выбор товара для редактирования
        elif query.data == "select_edit_item":
            await display_item_selection(query, user_id)
            return SELECT_EDIT_ITEM

        # Действие: Предварительный просмотр перед отправкой
        elif query.data == "final_preview":
            # Формируем предварительный просмотр накладной
            preview_text = format_final_invoice(user_data[user_id])

            # Создаем клавиатуру для подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("Confirm & Send", callback_data="confirm"),
                    InlineKeyboardButton("Edit Items", callback_data="select_edit_item"),
                ],
                [InlineKeyboardButton("Back to Main", callback_data="back_to_main")],
                [InlineKeyboardButton("Cancel", callback_data="cancel_process")],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=preview_text, reply_markup=reply_markup)

            return FINAL_CONFIRMATION

        # Действие: Возврат к основному экрану
        elif query.data == "back_to_main":
            message_text = format_invoice_data(user_data[user_id])

            # Создаем клавиатуру для действий
            keyboard = []

            # Проверяем наличие неопознанных товаров
            unmatched_items = [
                item
                for item in user_data[user_id]["matched_data"].get("lines", [])
                if item.get("product_id") is None
            ]

            if unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Fix Unrecognized Items", callback_data="edit_unmatched")]
                )

            keyboard.append(
                [InlineKeyboardButton("Review & Edit Items", callback_data="select_edit_item")]
            )

            if not unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Confirm & Preview Final", callback_data="final_preview")]
                )

            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_process")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=message_text, reply_markup=reply_markup)
            return CONFIRMATION

        return CONFIRMATION

    except Exception as e:
        error_msg = f"Error in handle_confirmation: {e}"
        log_error(error_msg, exc_info=True)

        try:
            await query.edit_message_text(
                text=f"❌ An error occurred. Please try again or start over with /cancel."
            )
        except Exception as inner_e:
            log_error(f"Error sending error message: {inner_e}", exc_info=True)

        return WAIT_PHOTO
