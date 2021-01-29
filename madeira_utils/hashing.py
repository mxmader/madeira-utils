import base64
import hashlib


def get_base64_digest(hash_object):
    return base64.b64encode(hash_object.digest()).decode("utf-8")


def get_base64_sum_of_data(data, hash_type='sha256'):
    hash_object = get_hash_object(hash_type)
    hash_object.update(data)
    return get_base64_digest(hash_object)


def get_hash_object(hash_type):
    hash_function = getattr(hashlib, hash_type)
    return hash_function()


def get_hex_sum_of_data(data, hash_type='sha256'):
    hash_object = get_hash_object(hash_type)
    hash_object.update(data.encode('utf-8'))
    return hash_object.hexdigest()
