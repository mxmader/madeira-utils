import importlib
import json

from madeira import s3
from madeira_utils import aws_lambda_responses


def enforce_content_length_2048(func):
    """Decorator which will return a bad request in the event of content length limit overrun."""
    def wrapper(context, logger):
        limit = 2048
        content_length = int(context.headers.get('Content-Length', 0))
        if context.body and (content_length > limit or len(context.body) > limit):
            error = (
                f"Cannot process request; content length: {content_length} exceeds limit: {limit}"
            )
            logger.error(error)
            return aws_lambda_responses.get_bad_request_response(error)
        else:
            return func(context, logger)

    return wrapper


class ApiCommon(object):
    def __init__(self, event, logger):
        self._logger = logger
        self._s3 = s3.S3()

        self.body = event.get('body')
        self.http_method = event['requestContext']['http']['method']
        self.params = event.get('queryStringParameters', {})
        self.path = event['requestContext']['http']['path']
        self.headers = event['headers']

    def process_request(self, context):
        # Useful for CloudWatch logging
        self._logger.info('Processing %s %s', self.http_method, self.path)
        module_name = f"endpoints.{self.path.replace('/api/', '').replace('/', '.')}"

        self._logger.debug('Using module: %s to route request for path: %s', module_name, self.path)
        module = importlib.import_module(module_name)
        function = getattr(module, self.http_method.lower())

        if self.body:
            try:
                self.body = json.loads(self.body)

            # if the body cannot be JSON decoded, don't pass it on
            except json.JSONDecodeError:
                self._logger.error('Could not JSON decode request body:')
                self._logger.debug(self.body)
                self.body = ''

        context.params = self.params
        context.body = self.body
        context.headers = self.headers

        return function(context, self._logger)


class ApiS3Wrapper(object):
    def __init__(self, logger):
        self._logger = logger
        self._s3 = s3.S3()

    def get_object_from_s3(self, bucket_name, object_key):
        self._s3 = s3.S3()

        try:
            return self._s3.get_object_contents(
                bucket_name,
                object_key,
                is_json=True
            )
        except self._s3.s3_client.exceptions.NoSuchKey:
            return {}

    def get_api_object_from_s3(self, object_key, context):
        return self.get_object_from_s3(
            context.api_persistence_bucket,
            object_key
        )

    def get_user_object_from_s3(self, namespace, context):
        if not context.user_hash:
            self._logger.debug(
                "Cannot get object in namespace: '%s' - user hash is unknown",
                namespace
            )
            return {}

        return self.get_object_from_s3(
            context.api_persistence_bucket,
            f"{namespace}/{context.user_hash}"
        )

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
