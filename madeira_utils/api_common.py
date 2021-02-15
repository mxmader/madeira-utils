from madeira import s3
from madeira_utils import aws_lambda_responses


# TODO: abstract class?
class ApiCommon(object):
    def __init__(self, logger):
        self._logger = logger
        self._s3 = s3.S3()

    def enforce_content_length(self, http_method, path, content_length, manifest):
        limit = manifest.get(f'{http_method} {path}')

        if limit and content_length > limit:
            error = f"Cannot process request; content length: {content_length} exceeds limit: {limit}"
            self._logger.error(error)
            return True, aws_lambda_responses.get_bad_request_response(error)

        return False, None

    def get_user_object_from_s3(self, namespace, context):
        if not context.user_hash:
            self._logger.debug("Cannot get object in namespace: '%s' - user hash is unknown", namespace)
            return {}

        self._s3 = s3.S3()
        object_key = f"{namespace}/{context.user_hash}"

        try:
            return self._s3.get_object_contents(context.api_persistence_bucket, object_key, is_json=True)
        except self._s3.s3_client.exceptions.NoSuchKey:
            return {}

    # noinspection PyUnusedLocal
    def get_response_for_object_get(self, namespace, context):
        return aws_lambda_responses.get_json_response(
            self.get_user_object_from_s3(namespace, context)
        )

    # noinspection PyUnusedLocal
    def get_response_for_object_put(self, namespace, body, context):
        self.write_user_object_to_s3(namespace, context, body)
        return aws_lambda_responses.get_json_response({'result': f'{namespace.title()} have been updated!'})

    def write_user_object_to_s3(self, namespace, context, body):
        self._s3 = s3.S3()
        object_key = f"{namespace}/{context.user_hash}"
        return self._s3.put_object(context.api_persistence_bucket, object_key, body, as_json=True)
