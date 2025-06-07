import logging
from csv_to_xml_converter.logger import setup_logger


def test_setup_logger_creates_log_file(tmp_path):
    log_file = tmp_path / "log.txt"
    cfg = {"logging": {"log_file": str(log_file), "log_level": "DEBUG"}}
    target_logger = logging.getLogger("test_logger")
    target_logger.handlers.clear()
    target_logger.propagate = False
    logger = setup_logger(config=cfg, logger_name="test_logger")
    logger.debug("debug message")
    logger.info("info message")
    for h in logger.handlers:
        if hasattr(h, "flush"):
            h.flush()
    assert log_file.exists()
    content = log_file.read_text()
    assert "debug message" in content
    assert "info message" in content
