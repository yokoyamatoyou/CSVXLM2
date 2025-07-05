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


def test_setup_logger_force_reconfigure(tmp_path):
    log_file1 = tmp_path / "one.log"
    cfg1 = {"logging": {"log_file": str(log_file1), "console": False}}
    target_logger = logging.getLogger("reconf")
    target_logger.handlers.clear()
    target_logger.propagate = False
    logger = setup_logger(config=cfg1, logger_name="reconf")
    logger.info("first")
    for h in logger.handlers:
        if hasattr(h, "flush"):
            h.flush()

    assert log_file1.exists()
    assert "first" in log_file1.read_text()

    log_file2 = tmp_path / "two.log"
    cfg2 = {"logging": {"log_file": str(log_file2), "console": False}}
    logger = setup_logger(config=cfg2, logger_name="reconf", force_reconfigure=True)
    logger.info("second")
    for h in logger.handlers:
        if hasattr(h, "flush"):
            h.flush()

    assert "second" not in log_file1.read_text()
    assert log_file2.exists()
    assert "second" in log_file2.read_text()
