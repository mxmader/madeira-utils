import json
import os

from madeira_utils import dns, loggers
import requests


class GoDaddyDns(object):

    api_url = "https://api.godaddy.com/v1/domains"

    def __init__(self, logger=None):
        self._logger = logger if logger else loggers.get_logger()
        config = json.load(open(os.path.expanduser("~/.godaddy-dns.json"), 'r'))
        self._domain = config['domain']
        self._base_api_url = f"{GoDaddyDns.api_url}/{self._domain}/records"
        self._dns = dns.Dns(logger=self._logger)
        self._session = requests.Session()
        self._session.headers = dict(
            Authorization=f"sso-key {config['api_key']}:{config['api_secret']}"
        )

    @staticmethod
    def _validate_change(record_type):
        if record_type in ['MX', 'SOA', 'NS']:
            raise RuntimeError('Record type %s not supported by this module', record_type)

    def assure_value(self, name, value, record_type, ttl=600):
        if self.get_value(name, record_type) == value:
            self._logger.info("%s is already set to %s in GoDaddy DNS", name, value)
        else:
            self.update_value(name, value, record_type, ttl=ttl)
        self._dns.wait_for_dns(name, value, record_type)

    def delete_value(self, name, record_type):
        self._validate_change(record_type)

        if not self.get_value(name, record_type):
            self._logger.info('%s %s does not exist (has no value) in GoDaddy DNS', record_type, name)
            return True

        r = self._session.get(self.get_api_url_for_record_type(record_type))
        r.raise_for_status()
        records_list = r.json()

        if len(records_list) == 1:
            self._logger.error("Since GoDaddy's DNS API requires at least one record of a given type to exist when "
                               "updating that type's list of records and there is only one record left of type %s, "
                               "we cannot delete that record via API.", record_type)
            return False

        short_name = self._dns.get_short_name(name, self._domain)
        records_to_retain = []

        for record in records_list:
            if record['name'] != short_name:
                records_to_retain.append(record)
            else:
                self._logger.debug("Dropping record for %s from list to retain", record['name'])

        if len(records_to_retain) != len(records_list) - 1:
            self._logger.error('List of records to retain was not composed as expected')
            return False

        self._logger.info(
            "Removing %s %s in GoDaddy DNS by replacing with list of only records to retain", record_type, name)
        r = self._session.put(
            self.get_api_url_for_record_type('CNAME'), json=records_to_retain)
        r.raise_for_status()
        return True

    def get_value(self, name, record_type):
        self._logger.debug("Getting value of %s %s via GoDaddy DNS", record_type, name)
        r = self._session.get(
            self.get_api_url_for_record(record_type, name))
        r.raise_for_status()
        result = r.json()
        return result[0]['data'] if result else ''

    def get_api_url_for_record(self, record_type, name):
        return f"{self._base_api_url}/{record_type}/{self._dns.get_short_name(name, self._domain)}"

    def get_api_url_for_record_type(self, record_type):
        return f"{self._base_api_url}/{record_type}"

    def update_value(self, name, value, record_type, ttl=600):
        self._validate_change(record_type)

        data = [{
            'name': name,
            'type': record_type,
            'data': value,
            'ttl': ttl
        }]
        self._logger.info("Setting %s %s to %s in GoDaddy DNS", record_type, name, value)
        r = self._session.put(
            self.get_api_url_for_record('CNAME', self._dns.get_short_name(name, self._domain)),
            json=data)
        r.raise_for_status()
        return True
