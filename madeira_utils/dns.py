import re
import time

import dns.resolver
from madeira_utils import loggers


class Dns(object):

    def __init__(self, logger=None):
        self._logger = logger if logger else loggers.get_logger()

    def get_short_name(self, name, domain):
        # along with the domain name, remove the leading and optionally trailing dots around the domain name
        # from the record in question
        short_name = re.sub(rf"\.{domain}\.*", '', name)
        self._logger.debug('%s was shortened to %s given domain %s', name, short_name, domain)
        return short_name

    def wait_for_dns(self, hostname, desired_value, record_type):
        if record_type == 'CNAME' and not desired_value.endswith('.'):
            desired_value = f"{desired_value}."

        for x in range(0, 50):

            try:
                answers = dns.resolver.resolve(hostname, record_type)

                # this does not currently support multiple values (i.e. round-robin DNS)
                dns_value = str(answers[0].target)

                if dns_value == desired_value:
                    self._logger.info('%s = %s via DNS query from this system', hostname, desired_value)
                    return
                self._logger.info('%s = %s but waiting for %s', hostname, dns_value, desired_value)

            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN) as e:
                self._logger.info('%s does not yet exist', hostname)
                self._logger.debug('exception message: %s', e)

            time.sleep(30)
