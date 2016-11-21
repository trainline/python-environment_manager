""" Copyright (c) Trainline Limited, 2016. All rights reserved. See LICENSE.txt in the project root for license information. """
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

import traceback
import logging
import simplejson

class LogWrapper(object):
    """ Instanciates logging wrapper to add useful information to all logs without repeating code """

    def __init__(self):
        """ Initialise logger """
        self.logger = logging.getLogger(__name__)

    def debug(self, message):
        """ Debug """
        self.logger.debug("%s - %s", function_name(), message)

    def info(self, message):
        """ Info """
        self.logger.info("%s - %s", function_name(), message)

    def warn(self, message):
        """ Warn """
        self.logger.warn("%s - %s", function_name(), message)

    def error(self, message):
        """ Error """
        self.logger.error("%s - %s", function_name(), message, exc_info=True)

    def critical(self, message):
        """ Critical """
        self.logger.critical("%s - %s", function_name(), message, exc_info=True)

class LogWrapperMultiprocess(object):
    """ Instanciates logging wrapper to add useful information to all logs without repeating code """

    @classmethod
    def install_mp_handler(cls, logger=None):
        """Wraps the handlers in the given Logger with an MultiProcessingHandler.
        :param logger: whose handlers to wrap. By default, the root logger."""
        import multiprocessing_logging
        if logger is None:
            logger = logging.getLogger()
        for i, orig_handler in enumerate(list(logger.handlers)):
            handler = multiprocessing_logging.MultiProcessingHandler(
                'mp-handler-{0}'.format(i), sub_handler=orig_handler)
            logger.removeHandler(orig_handler)
            logger.addHandler(handler)

    def __init__(self):
        """ Initialise logger """
        self.logger = logging.getLogger()
        self.install_mp_handler()

    @classmethod
    def process_name(cls):
        """ Return current process name for multithreaded envs """
        import multiprocessing
        mp_name = multiprocessing.current_process().name
        if mp_name is None:
            mp_name = "Main"
        return mp_name

    def debug(self, message):
        """ Debug """
        self.logger.debug("%s %s - %s", self.process_name(), function_name(), message)

    def info(self, message):
        """ Info """
        self.logger.info("%s %s - %s", self.process_name(), function_name(), message)

    def warn(self, message):
        """ Warn """
        self.logger.warn("%s %s - %s", self.process_name(), function_name(), message)

    def error(self, message):
        """ Error """
        self.logger.error("%s %s - %s", self.process_name(), function_name(), message, exc_info=True)

    def critical(self, message):
        """ Critical """
        self.logger.critical("%s %s - %s", self.process_name(), function_name(), message, exc_info=True)

def to_bool(value):
    """Converts 'something' to boolean. Raises exception for invalid formats
   Possible True  values: 1, True, "1", "TRue", "yes", "y", "t"
   Possible False values: 0, False, None, [], {}, "", "0", "faLse", "no", "n", "f", 0.0, ..."""
    if str(value).lower() in ("yes", "y", "true", "t", "1"):
        return True
    if str(value).lower() in ("no", "n", "false", "f", "0", "0.0", "", "none", "[]", "{}"):
        return False
    raise Exception('Invalid value for boolean conversion: ' + str(value))

def to_list(value):
    """ Create an array from any kind of object """
    initial_list = [x.strip() for x in value.translate(None, '!@#$[]{}\'"').split(',')]
    return [x for x in initial_list if x]

def function_name():
    """ Return the name of the function calling this code """
    return traceback.extract_stack(None, 3)[0][2]

def json_encode(input_object):
    """ Encode and returns a JSON stream """
    return simplejson.dumps(input_object)

def json_decode(string):
    """ Decode a JSON stream and returns a python dictionary version """
    log = LogWrapper()
    try:
        decoded_json = simplejson.loads(string)
    except simplejson.JSONDecodeError:
        log.error('Can\'t decode JSON string: %s' % string)
        return None
    return decoded_json
