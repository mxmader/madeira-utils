import base64
import hashlib
import io
import json
import os
import time
import zipfile

import dns.resolver
import madeira_utils
import requests


class Utils(object):

    def __init__(self, logger=None):
        self._logger = logger if logger else madeira_utils.get_logger()

    @staticmethod
    def get_base64_digest(hash_object):
        return base64.b64encode(hash_object.digest()).decode("utf-8")

    def get_base64_sum_of_file(self, file, hash_type='sha256'):
        hash_object = self.get_hash_object(hash_type)
        with open(file, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                hash_object.update(data)
        return self.get_base64_digest(hash_object)

    def get_base64_sum_of_data(self, data, hash_type='sha256'):
        hash_object = self.get_hash_object(hash_type)
        hash_object.update(data)
        return self.get_base64_digest(hash_object)

    def get_base64_sum_of_stream(self, stream, hash_type='sha256', block_size=1048576):
        hash_object = self.get_hash_object(hash_type)
        while True:
            buffer = stream.read(block_size)
            if not buffer:
                break
            hash_object.update(buffer)
        return self.get_base64_digest(hash_object)

    def get_base64_sum_of_file_in_zip_from_url(self, url, file_name_in_zip, hash_type='sha256'):
        r = requests.get(url)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        return self.get_base64_sum_of_data(z.read(file_name_in_zip), hash_type=hash_type)

    def get_godaddy_dns_value(self, name, record_type):
        config = json.load(open(os.path.expanduser("~/.godaddy-dns.json"), 'r'))
        name = name.replace(f".{config['domain']}", '')
        self._logger.info("Getting value of %s %s via GoDaddy DNS", record_type, name)
        r = requests.get(
            f"https://api.godaddy.com/v1/domains/{config['domain']}/records/{record_type}/{name}",
            headers={'Authorization': f"sso-key {config['api_key']}:{config['api_secret']}"}
        )
        result = r.json()
        return result[0]['data']

    @staticmethod
    def get_hash_object(hash_type):
        hash_function = getattr(hashlib, hash_type)
        return hash_function()

    def get_file_content(self, file, binary=False):
        mode = 'rb' if binary else 'r'
        self._logger.debug('Opening %s in mode: %s', file, mode)
        with open(file, mode) as f:
            file_content = f.read()

        # return outside context manager to ensure file handle is closed
        return file_content

    @staticmethod
    def get_files_in_path(path, skip_roots_containing=None):
        file_list = []
        for root, dirs, files in os.walk(path):
            if (skip_roots_containing and skip_roots_containing in root) or not files:
                continue
            for file in files:
                file_list.append({'name': file, 'root': root})
        return file_list

    def get_template_body(self, template_name, template_dir='cf_templates/'):
        return self.get_file_content(f"{template_dir}{template_name}.yml")

    def get_zip_content(self, function_file_path):
        if function_file_path.endswith('.zip'):
            with open(function_file_path, 'rb') as f:
                zip_file_content = f.read()
        else:
            in_memory_zip = self.get_function_zip(function_file_path)
            zip_file_content = in_memory_zip.getvalue()

        return zip_file_content

    @staticmethod
    def get_zip_object():
        in_memory_zip = io.BytesIO()
        zip_file = zipfile.ZipFile(in_memory_zip, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=False)
        return in_memory_zip, zip_file

    def get_function_zip(self, function_file_path, file_in_zip='handler.py'):
        in_memory_zip, zip_file = self.get_zip_object()

        with open(function_file_path, 'r') as f:
            file_content = f.read()

        # from https://forums.aws.amazon.com/thread.jspa?threadID=239601
        zip_info = zipfile.ZipInfo(file_in_zip)
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zip_info.create_system = 3  # Specifies Unix
        zip_info.external_attr = 0o0777 << 16  # adjusted for python 3
        zip_file.writestr(zip_info, file_content)
        zip_file.close()

        # move file cursor to start of in-memory zip file for purposes of uploading to AWS
        in_memory_zip.seek(0)
        return in_memory_zip

    def get_layer_zip(self, layer_path):
        in_memory_zip, zip_file = self.get_zip_object()

        cwd = os.getcwd()
        os.chdir(layer_path)
        files = self.get_files_in_path('.', skip_roots_containing='__pycache__')

        # add each file in the layer to the in-memory zip
        for file in files:
            file_path = f"{file['root']}/{file['name']}"
            with open(file_path, 'r') as f:
                file_content = f.read()
            zip_info = zipfile.ZipInfo(file_path)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            zip_info.create_system = 3  # Specifies Unix
            zip_info.external_attr = 0o0777 << 16  # adjusted for python 3
            zip_file.writestr(zip_info, file_content)

        os.chdir(cwd)
        zip_file.close()
        in_memory_zip.seek(0)
        return in_memory_zip

    def update_godaddy_dns_record(self, name, value, record_type, ttl=600):
        config = json.load(open(os.path.expanduser("~/.godaddy-dns.json"), 'r'))
        name = name.replace(f".{config['domain']}", '')
        data = [{
            'name': name,
            'type': record_type,
            'data': value,
            'ttl': ttl
        }]
        self._logger.info("Setting %s %s to %s in GoDaddy DNS", record_type, name, value)
        r = requests.put(
            f"https://api.godaddy.com/v1/domains/{config['domain']}/records/{record_type}/{name}",
            headers={'Authorization': f"sso-key {config['api_key']}:{config['api_secret']}"},
            json=data)
        r.raise_for_status()

    def wait_for_dns(self, hostname, desired_value, record_type):
        for x in range(0, 50):

            try:
                answers = dns.resolver.resolve(hostname, record_type)
                # this does not support multiple values as-written
                dns_value = str(answers[0].target)
                if dns_value == f'{desired_value}.':
                    self._logger.info('%s = %s via DNS query from this system', hostname, desired_value)
                    return

                self._logger.info('%s = %s but we want %s', hostname, dns_value, desired_value)

            except dns.resolver.NXDOMAIN:
                self._logger.debug('%s does not yet exist', hostname)

            time.sleep(30)
