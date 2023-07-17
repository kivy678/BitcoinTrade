# -*- coding:utf-8 -*-

#############################################################################

import os, sys
import timeit

import logging
import logging.handlers

#############################################################################

LOGFMT_STRING = "%(asctime)-15s|%(levelname)s|%(filename)s|%(lineno)d|%(module)s|%(funcName)s|%(message)s"
LOGFMT = logging.Formatter(LOGFMT_STRING)

def getLogger(name, LOG_FILE, stream=False):

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    fileHandler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=32 * 1024 * 1024, backupCount=3
    )
    if stream:
        streamHandler = logging.StreamHandler()
        streamHandler.setFormatter(LOGFMT)
        logger.addHandler(streamHandler)

    fileHandler.setFormatter(LOGFMT)
    logger.addHandler(fileHandler)

    return logger


LOGGER_PATH = os.path.join('LOG', 'report')
LOG = getLogger('Report', LOGGER_PATH, False)
