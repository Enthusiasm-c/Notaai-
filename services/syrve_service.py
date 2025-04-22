import asyncio
import datetime
import hashlib
import logging
import os
import xml.etree.ElementTree as ET

import aiohttp
from dotenv import load_dotenv

from utils.error_handling import log_error

# Загрузка переменных окружения
load_dotenv()

# Получаем логгер
logger = logging.getLogger(__name__)

# Кэш для токена аутентификации
auth_token = None
auth_token_expiry = None


async def authenticate():
    """
    Аутентификация в Syrve API

    Returns:
        str: Токен авторизации или None при ошибке
    """
    global auth_token, auth_token_expiry

    # Проверяем, есть ли у нас действующий токен
    if auth_token and auth_token_expiry and datetime.datetime.now() < auth_token_expiry:
        logger.info("Using cached auth token")
        return auth_token

    # Получаем параметры аутентификации
    server_url = os.getenv("SYRVE_SERVER_URL")
    login = os.getenv("SYRVE_LOGIN")
    password = os.getenv("SYRVE_PASSWORD")

    if not server_url or not login or not password:
        log_error("Missing Syrve API credentials in environment variables")
        return None

    try:
        # Хеширование пароля в соответствии с требованиями API
        password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()

        # Формируем URL для аутентификации
        auth_url = f"{server_url}/resto/api/auth?login={login}&pass={password_hash}"

        # Отправляем запрос
        async with aiohttp.ClientSession() as session:
            async with session.get(auth_url) as response:
                if response.status != 200:
                    response_text = await response.text()
                    log_error(f"Auth failed: HTTP {response.status}, {response_text}")
                    return None

                # Получаем токен из ответа
                response_text = await response.text()

                # Проверяем наличие токена
                try:
                    response_xml = ET.fromstring(response_text)
                    token_elem = response_xml.find(".//token")

                    if token_elem is not None:
                        auth_token = token_elem.text
                        # Устанавливаем срок действия токена на 1 час
                        auth_token_expiry = datetime.datetime.now() + datetime.timedelta(hours=1)
                        logger.info("Authentication successful")
                        return auth_token

                    log_error(f"Token not found in response: {response_text}")
                    return None
                except Exception as e:
                    log_error(f"Error parsing auth response: {e}", exc_info=True)
                    return None
    except Exception as e:
        log_error(f"Error during authentication: {e}", exc_info=True)
        return None


async def send_invoice_to_syrve(token, invoice_data):
    """
    Отправка накладной в Syrve API

    Args:
        token: Токен авторизации
        invoice_data: Данные накладной

    Returns:
        document_id: ID документа при успехе, None при ошибке
    """
    server_url = os.getenv("SYRVE_SERVER_URL")
    store_guid = os.getenv("SYRVE_STORE_GUID", "1239d270-1bbe-f64f-b7ea-5f00518ef508")

    # Создаем XML документ
    root = ET.Element("document")

    # Добавляем номер документа
    ET.SubElement(root, "documentNumber").text = invoice_data.get(
        "number", f"INV-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    # Добавляем элементы товаров
    items_elem = ET.SubElement(root, "items")

    for i, item in enumerate(invoice_data.get("items", []), start=1):
        item_elem = ET.SubElement(items_elem, "item")

        ET.SubElement(item_elem, "amount").text = f"{item['amount']:.3f}"
        ET.SubElement(item_elem, "product").text = item["product_id"]
        ET.SubElement(item_elem, "num").text = str(i)
        ET.SubElement(item_elem, "sum").text = f"{item['total']:.2f}"
        ET.SubElement(item_elem, "price").text = f"{item['price']:.2f}"
        ET.SubElement(item_elem, "store").text = store_guid
        ET.SubElement(item_elem, "actualAmount").text = f"{item['amount']:.3f}"

    # Добавляем дату
    ET.SubElement(root, "dateIncoming").text = invoice_data.get(
        "date", datetime.datetime.now().strftime("%d.%m.%Y")
    )

    # Добавляем склад по умолчанию (используем правильный GUID)
    ET.SubElement(root, "defaultStore").text = store_guid

    # Добавляем поставщика
    ET.SubElement(root, "supplier").text = invoice_data.get("supplier_id", "7")

    # Преобразуем XML в строку
    xml_data = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")

    # Логируем сформированный XML для отладки
    logger.info(f"Sending XML to Syrve API:\n{xml_data}")

    # Отправляем запрос
    url = f"{server_url}/resto/api/documents/import/incomingInvoice?key={token}"
    headers = {"Content-Type": "application/xml"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=xml_data, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    log_error(f"Failed to send invoice: HTTP {response.status}, {response_text}")
                    return None

                response_text = await response.text()
                logger.info(f"Syrve API response: {response_text}")

                # Извлекаем ID документа
                try:
                    response_xml = ET.fromstring(response_text)
                    document_id = response_xml.find(".//documentId")

                    if document_id is not None:
                        logger.info(f"Document ID: {document_id.text}")
                        return document_id.text

                    # Проверяем успешность валидации
                    valid_elem = response_xml.find(".//valid")
                    if valid_elem is not None and valid_elem.text.lower() == "true":
                        # Документ успешно отправлен, но ID не вернулся
                        document_number = invoice_data.get("number", "")
                        logger.info(f"Invoice successfully submitted: {document_number}")
                        return document_number

                    log_error(f"Could not get document ID from response: {response_text}")
                    return None
                except Exception as e:
                    log_error(f"Error parsing response XML: {e}", exc_info=True)
                    return None
    except Exception as e:
        log_error(f"Error sending invoice: {e}", exc_info=True)
        return None


async def commit_document(token, document_id):
    """
    Проведение документа в Syrve API

    Args:
        token: Токен авторизации
        document_id: ID документа

    Returns:
        bool: Успешно ли проведен документ
    """
    server_url = os.getenv("SYRVE_SERVER_URL")

    # Формируем URL для проведения документа
    url = f"{server_url}/resto/api/documents/commit?key={token}"

    # Создаем XML для запроса
    root = ET.Element("document")
    ET.SubElement(root, "id").text = document_id

    # Преобразуем XML в строку
    xml_data = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")

    # Отправляем запрос
    headers = {"Content-Type": "application/xml"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=xml_data, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    log_error(f"Failed to commit document: HTTP {response.status}, {response_text}")
                    return False

                response_text = await response.text()
                logger.info(f"Commit response: {response_text}")

                # Проверяем успешность проведения
                try:
                    response_xml = ET.fromstring(response_text)
                    success_elem = response_xml.find(".//success")

                    if success_elem is not None and success_elem.text.lower() == "true":
                        logger.info(f"Document {document_id} committed successfully")
                        return True

                    log_error(f"Failed to commit document: {response_text}")
                    return False
                except Exception as e:
                    log_error(f"Error parsing commit response: {e}", exc_info=True)
                    return False
    except Exception as e:
        log_error(f"Error committing document: {e}", exc_info=True)
        return False


async def get_stores(token):
    """
    Получение списка складов из Syrve API

    Args:
        token: Токен авторизации

    Returns:
        list: Список складов в формате [{'id': '...', 'name': '...'}]
    """
    server_url = os.getenv("SYRVE_SERVER_URL")

    # Формируем URL
    url = f"{server_url}/resto/api/corporation/stores?key={token}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response_text = await response.text()
                    log_error(f"Failed to get stores: HTTP {response.status}, {response_text}")
                    return []

                response_text = await response.text()

                # Парсим XML-ответ
                try:
                    response_xml = ET.fromstring(response_text)
                    stores = []

                    # Извлекаем данные о складах
                    for store_elem in response_xml.findall(".//corporationStore"):
                        store_id = store_elem.find("id")
                        store_name = store_elem.find("name")

                        if store_id is not None and store_name is not None:
                            stores.append({"id": store_id.text, "name": store_name.text})

                    logger.info(f"Retrieved {len(stores)} stores")
                    return stores
                except Exception as e:
                    log_error(f"Error parsing stores response: {e}", exc_info=True)
                    return []
    except Exception as e:
        log_error(f"Error getting stores: {e}", exc_info=True)
        return []


async def get_products(token):
    """
    Получение списка товаров из Syrve API

    Args:
        token: Токен авторизации

    Returns:
        list: Список товаров
    """
    server_url = os.getenv("SYRVE_SERVER_URL")

    # Формируем URL
    url = f"{server_url}/resto/api/v2/entities/products/list?includeDeleted=false&key={token}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response_text = await response.text()
                    log_error(f"Failed to get products: HTTP {response.status}, {response_text}")
                    return []

                response_text = await response.text()

                # Парсим XML-ответ
                try:
                    response_xml = ET.fromstring(response_text)
                    products = []

                    # Извлекаем данные о товарах
                    for product_elem in response_xml.findall(".//product"):
                        product_id = product_elem.find("id")
                        product_name = product_elem.find("name")

                        if product_id is not None and product_name is not None:
                            products.append({"id": product_id.text, "name": product_name.text})

                    logger.info(f"Retrieved {len(products)} products")
                    return products
                except Exception as e:
                    log_error(f"Error parsing products response: {e}", exc_info=True)
                    return []
    except Exception as e:
        log_error(f"Error getting products: {e}", exc_info=True)
        return []
