import json
import logging
import os
from typing import Dict, Optional

# Set up logging
logger = logging.getLogger(__name__)

# In-memory cache - инициализируем в начале файла до первого использования
learned_mappings: Dict[str, str] = {}
unit_conversions: Dict[str, Dict[str, float]] = {}

# Paths to storage files
MAPPINGS_FILE = os.path.join("data", "learned_mappings.json")
UNITS_FILE = os.path.join("data", "unit_conversions.json")


def load_learned_mappings() -> Dict[str, str]:
    """
    Load learned mappings from file

    Returns:
        dict: Learned mappings (item_name -> product_id)
    """
    global learned_mappings

    # If cache is already populated, return it
    if learned_mappings:
        return learned_mappings

    # Check if file exists
    if not os.path.exists(MAPPINGS_FILE):
        logger.info(f"Learned mappings file not found: {MAPPINGS_FILE}")
        return {}

    try:
        with open(MAPPINGS_FILE, "r", encoding="utf-8") as f:
            loaded_mappings = json.load(f)

        # Store in cache
        learned_mappings = loaded_mappings
        logger.info(f"Loaded {len(learned_mappings)} learned mappings")
        return learned_mappings
    except Exception as e:
        logger.error(f"Error loading learned mappings: {e}", exc_info=True)
        return {}


def save_learned_mapping(item_name: str, product_id: str) -> bool:
    """
    Save a new learned mapping

    Args:
        item_name: Raw item name from invoice
        product_id: Matched product ID

    Returns:
        bool: Success status
    """
    global learned_mappings

    try:
        # Load existing mappings
        mappings = load_learned_mappings()

        # Add new mapping
        mappings[item_name] = product_id

        # Ensure directory exists
        os.makedirs(os.path.dirname(MAPPINGS_FILE), exist_ok=True)

        # Save to file
        with open(MAPPINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(mappings, f, ensure_ascii=False, indent=2)

        # Update cache
        learned_mappings = mappings

        logger.info(f"Saved new mapping: '{item_name}' -> {product_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving learned mapping: {e}", exc_info=True)
        return False


def get_product_id_from_mapping(item_name: str) -> Optional[str]:
    """
    Get product ID from learned mappings

    Args:
        item_name: Raw item name from invoice

    Returns:
        str: Product ID if found, None otherwise
    """
    # Load mappings
    mappings = load_learned_mappings()

    # Look for exact match
    if item_name in mappings:
        logger.info(f"Found mapping for '{item_name}': {mappings[item_name]}")
        return mappings[item_name]

    # Look for case-insensitive match
    item_lower = item_name.lower()
    for key, value in mappings.items():
        if key.lower() == item_lower:
            logger.info(f"Found case-insensitive mapping for '{item_name}': {value}")
            return value

    logger.debug(f"No mapping found for '{item_name}'")
    return None


def load_unit_conversions() -> Dict[str, Dict[str, float]]:
    """
    Load unit conversions from file

    Returns:
        dict: Unit conversions
    """
    global unit_conversions

    # If cache is already populated, return it
    if unit_conversions:
        return unit_conversions

    # Check if file exists
    if not os.path.exists(UNITS_FILE):
        logger.info(f"Unit conversions file not found: {UNITS_FILE}")
        return {}

    try:
        with open(UNITS_FILE, "r", encoding="utf-8") as f:
            loaded_conversions = json.load(f)

        # Store in cache
        unit_conversions = loaded_conversions
        logger.info(f"Loaded unit conversions for {len(unit_conversions)} units")
        return unit_conversions
    except Exception as e:
        logger.error(f"Error loading unit conversions: {e}", exc_info=True)
        return {}


def save_unit_conversion(from_unit: str, to_unit: str, factor: float) -> bool:
    """
    Save a new unit conversion

    Args:
        from_unit: Source unit
        to_unit: Target unit
        factor: Conversion factor

    Returns:
        bool: Success status
    """
    try:
        # Load existing conversions
        conversions = load_unit_conversions()

        # Initialize the unit if not present
        if from_unit not in conversions:
            conversions[from_unit] = {}

        # Add conversion
        conversions[from_unit][to_unit] = factor

        # Add reciprocal if not present
        if to_unit not in conversions:
            conversions[to_unit] = {}
        conversions[to_unit][from_unit] = 1.0 / factor

        # Ensure directory exists
        os.makedirs(os.path.dirname(UNITS_FILE), exist_ok=True)

        # Save to file
        with open(UNITS_FILE, "w", encoding="utf-8") as f:
            json.dump(conversions, f, ensure_ascii=False, indent=2)

        # Update cache
        global unit_conversions
        unit_conversions = conversions

        logger.info(f"Saved new unit conversion: {from_unit} -> {to_unit} (factor: {factor})")
        return True
    except Exception as e:
        logger.error(f"Error saving unit conversion: {e}", exc_info=True)
        return False


def convert_unit(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    """
    Convert value between units

    Args:
        value: Value to convert
        from_unit: Source unit
        to_unit: Target unit

    Returns:
        float: Converted value if possible, None otherwise
    """
    # If units are the same, no conversion needed
    if from_unit == to_unit:
        return value

    # Load conversions
    conversions = load_unit_conversions()

    # Check if direct conversion exists
    if from_unit in conversions and to_unit in conversions[from_unit]:
        factor = conversions[from_unit][to_unit]
        logger.debug(f"Converting {value} {from_unit} to {to_unit} (factor: {factor})")
        return value * factor

    # No conversion found
    logger.warning(f"No conversion found from {from_unit} to {to_unit}")
    return None
