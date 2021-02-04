import io
import os
import zipfile

from madeira_utils import hashing
import requests
import yaml


def get_base64_sum_of_file(file, hash_type='sha256'):
    hash_object = hashing.get_hash_object(hash_type)
    with open(file, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            hash_object.update(data)
    return hashing.get_base64_digest(hash_object)


def get_base64_sum_of_stream(stream, hash_type='sha256', block_size=1048576):
    hash_object = hashing.get_hash_object(hash_type)
    while True:
        buffer = stream.read(block_size)
        if not buffer:
            break
        hash_object.update(buffer)
    return hashing.get_base64_digest(hash_object)


def get_base64_sum_of_file_in_zip_from_url(url, file_name_in_zip, hash_type='sha256'):
    r = requests.get(url)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return hashing.get_base64_sum_of_data(z.read(file_name_in_zip), hash_type=hash_type)


def get_file_content(file, binary=False):
    mode = 'rb' if binary else 'r'
    with open(file, mode) as f:
        file_content = f.read()

    # return outside context manager to ensure file handle is closed
    return file_content


def get_files_in_path(path, skip_roots_containing=None):
    file_list = []
    for root, dirs, files in os.walk(path):
        if (skip_roots_containing and skip_roots_containing in root) or not files:
            continue
        for file in files:
            file_list.append({'name': file, 'root': root})
    return file_list


def get_function_zip(function_file_path, file_in_zip='handler.py'):
    in_memory_zip, zip_file = get_zip_object()

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


def get_layer_zip(layer_path):
    in_memory_zip, zip_file = get_zip_object()

    cwd = os.getcwd()
    os.chdir(layer_path)
    files = get_files_in_path('.', skip_roots_containing='__pycache__')

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


def get_cf_template_for_module(module_spec):
    module_name = module_spec.name.split('.')[-1]
    return get_template_body(module_name, template_dir=f"{os.path.dirname(module_spec.origin)}/cf_templates/")


def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f.read())


def get_template_body(template_name, template_dir='cf_templates/'):
    return get_file_content(f"{template_dir}{template_name}.yml")


def get_zip_content(function_file_path):
    if function_file_path.endswith('.zip'):
        with open(function_file_path, 'rb') as f:
            zip_file_content = f.read()
    else:
        in_memory_zip = get_function_zip(function_file_path)
        zip_file_content = in_memory_zip.getvalue()

    return zip_file_content


def get_zip_object():
    in_memory_zip = io.BytesIO()
    zip_file = zipfile.ZipFile(in_memory_zip, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=False)
    return in_memory_zip, zip_file
