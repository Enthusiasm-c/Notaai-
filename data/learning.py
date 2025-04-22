import csv
import logging
import os

from config import LEARNED_MAPPINGS_FILE, UNIT_CONVERSIONS_FILE
from utils.error_handling import log_error

# Получаем логгер
logger = logging.getLogger(__name__)

# Глобальные переменные для хранения обученных данных
learned_mappings = {}
unit_conversions = {}


def load_learned_mappings():
    """
    Загрузка сопоставлений товаров из CSV файла

    Returns:
        dict: Словарь сопоставлений
    """
    global learned_mappings

    if not os.path.exists(LEARNED_MAPPINGS_FILE):
        # Создаем файл с заголовками, если он не существует
        os.makedirs(os.path.dirname(LEARNED_MAPPINGS_FILE), exist_ok=True)
        with open(LEARNED_MAPPINGS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["original_name", "product_id", "corrected_name"])
        return {}

    mappings = {}
    try:
        with open(LEARNED_MAPPINGS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                original_name = row.get("original_name", "").lower()
                if original_name:
                    mappings[original_name] = {
                        "product_id": row.get("product_id", ""),
                        "corrected_name": row.get("corrected_name", ""),
                    }
        logger.info(
            f"Loaded {len(mappings)} learned mappings from {LEARNED_MAPPINGS_FILE}"
        )
        learned_mappings = mappings
        return mappings
    except Exception as e:
        log_error(f"Error loading learned mappings: {e}", exc_info=True)
        return {}


def load_unit_conversions():
    """
    Загрузка конвертаций единиц измерения из CSV файла

    Returns:
        dict: Словарь конвертаций
    """
    global unit_conversions

    if not os.path.exists(UNIT_CONVERSIONS_FILE):
        # Создаем файл с заголовками, если он не существует
        os.makedirs(os.path.dirname(UNIT_CONVERSIONS_FILE), exist_ok=True)
        with open(UNIT_CONVERSIONS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "product_id",
                    "product_name",
                    "source_unit",
                    "target_unit",
                    "conversion_factor",
                ]
            )
        return {}

    conversions = {}
    try:
        with open(UNIT_CONVERSIONS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_id = row.get("product_id", "")
                source_unit = row.get("source_unit", "").lower()
                if product_id and source_unit:
                    key = (product_id, source_unit)
                    conversions[key] = {
                        "product_name": row.get("product_name", ""),
                        "target_unit": row.get("target_unit", ""),
                        "conversion_factor": float(row.get("conversion_factor", 1.0)),
                    }
        logger.info(
            f"Loaded {len(conversions)} unit conversions from {UNIT_CONVERSIONS_FILE}"
        )
        unit_conversions = conversions
        return conversions
    except Exception as e:
        log_error(f"Error loading unit conversions: {e}", exc_info=True)
        return {}


def save_learned_mapping(original_name, product_id, corrected_name):
    """
    Сохранение сопоставления товара в CSV файл

    Args:
        original_name: Оригинальное название товара
        product_id: ID товара в базе данных
        corrected_name: Скорректированное название

    Returns:
        bool: Успешно ли сохранено сопоставление
    """
    global learned_mappings

    try:
        file_exists = os.path.exists(LEARNED_MAPPINGS_FILE)

        with open(LEARNED_MAPPINGS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Записываем заголовки, если файл новый
            if not file_exists:
                writer.writerow(["original_name", "product_id", "corrected_name"])

            # Записываем новое сопоставление
            writer.writerow([original_name, product_id, corrected_name])

        # Обновляем сопоставления в памяти
        learned_mappings[original_name.lower()] = {
            "product_id": product_id,
            "corrected_name": corrected_name,
        }

        logger.info(
            f"Saved new mapping: {original_name} -> {corrected_name} (ID: {product_id})"
        )
        return True
    except Exception as e:
        log_error(f"Error saving learned mapping: {e}", exc_info=True)
        return False


def save_unit_conversion(
    product_id, product_name, source_unit, target_unit, conversion_factor
):
    """
    Сохранение конвертации единиц измерения в CSV файл

    Args:
        product_id: ID товара
        product_name: Название товара
        source_unit: Исходная единица измерения
        target_unit: Целевая единица измерения
        conversion_factor: Коэффициент конвертации

    Returns:
        bool: Успешно ли сохранена конвертация
    """
    global unit_conversions

    try:
        file_exists = os.path.exists(UNIT_CONVERSIONS_FILE)

        with open(UNIT_CONVERSIONS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Записываем заголовки, если файл новый
            if not file_exists:
                writer.writerow(
                    [
                        "product_id",
                        "product_name",
                        "source_unit",
                        "target_unit",
                        "conversion_factor",
                    ]
                )

            # Записываем новую конвертацию
            writer.writerow(
                [product_id, product_name, source_unit, target_unit, conversion_factor]
            )

        # Обновляем конвертации в памяти
        key = (product_id, source_unit.lower())
        unit_conversions[key] = {
            "product_name": product_name,
            "target_unit": target_unit,
            "conversion_factor": float(conversion_factor),
        }

        logger.info(
            f"Saved new unit conversion: {product_name} {source_unit} -> {target_unit} (factor: {conversion_factor})"
        )
        return True
    except Exception as e:
        log_error(f"Error saving unit conversion: {e}", exc_info=True)
        return False
