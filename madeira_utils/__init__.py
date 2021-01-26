import logging
import sys

__version__ = '1.0'


def get_logger(level=logging.INFO, use_stdout=True, logger_name='madeira_utils_logger'):
    logger = logging.getLogger(logger_name)

    # only override the logger-scoped level if we're making it more granular with this particular invocation
    if not logger.level or level < logger.level:
        logger.setLevel(level)

    # if we already have a handler, we're likely calling get_logger for the Nth time within a given process.
    if use_stdout and not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
