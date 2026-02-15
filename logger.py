import logging
import sys
from datetime import datetime

def setup_logger():
    """Setup logging configuration"""
    logger = logging.getLogger("github_automation")
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler("automation.log")
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger