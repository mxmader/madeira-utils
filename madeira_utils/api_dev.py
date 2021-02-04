import importlib
import json
import logging
import os
from wsgiref import simple_server

import falcon
from madeira_utils import loggers, utils


class FalconApiDev(object):

    def __init__(self, router_module):
        # Initialize the logger
        self._logger = loggers.get_logger(level=logging.DEBUG)
        self._logger.info('Loading API configuration from filesystem')
        self._api_config = utils.load_yaml('config.yaml')['test']

        if not self._api_config:
            raise RuntimeError("Could not load API configuration")

        self._request_router = RequestRouter(self._api_config, router_module, self._logger)

        self._logger.info(f'Initializing API using falcon {falcon.__version__}')
        self.api = falcon.API(middleware=[
            CorsPreflight(self._logger),
            MockDataResponse(self._logger),
            FormatResponse(self._logger)
        ])

        self._logger.info('API Initialized')

    def add_routes(self, routes):
        for route in routes:
            self.api.add_route(route, self._request_router)

    def serve_wsgi(self):
        webserver_bind_address = '0.0.0.0'
        webserver_port = 8080
        self._logger.debug('Launching webserver bound to %s:%s', webserver_bind_address, webserver_port)
        httpd = simple_server.make_server(webserver_bind_address, webserver_port, self.api)
        httpd.serve_forever()


class FalconMiddleware(object):

    def __init__(self, logger):
        self._logger = logger

    def log_request(self, req, resp):
        self._logger.info(
            '%s:%s:%s:%s',
            req.remote_addr,
            req.method,
            req.relative_uri,
            resp.status
        )

    def process_bad_request(self, error_message, req, resp):
        req.context.result = {'error': error_message}
        resp.status = falcon.HTTP_BAD_REQUEST
        self._logger.error(error_message)
        self.log_request(req, resp)


class CorsPreflight(FalconMiddleware):
    """Handle CORS preflight (OPTIONS) requests."""

    # noinspection PyUnusedLocal
    def process_request(self, req, resp):

        # this effectively permits CORS preflight requests only in development environments
        if req.host == 'localhost':
            self._logger.debug('processing request in development context')
            resp.set_header('Access-Control-Allow-Headers', '*')
            resp.set_header('Access-Control-Allow-Methods', '*')
            resp.set_header('Access-Control-Allow-Origin', req.get_header('Origin'))

            if req.method == 'OPTIONS':
                self._logger.debug('handling OPTIONS request as CORS preflight')
                resp.status = falcon.HTTP_OK
                raise falcon.http_status.HTTPStatus(falcon.HTTP_200, body='\n')


class FormatResponse(FalconMiddleware):

    # noinspection PyUnusedLocal
    @classmethod
    def process_request(cls, req, resp):
        if req.content_length in (None, 0):
            return
        req.context.data = req.stream.read().decode('utf-8')

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def process_response(self, req, resp, resource, req_succeeded):
        self.log_request(req, resp)


class MockDataResponse(FalconMiddleware):

    # noinspection PyUnusedLocal
    def process_request(self, req, resp):
        # simple yet crude way of returning mock data for any call
        if os.getenv("MOCK_DATA") == "true":
            self._logger.info('using mock data mode')

            body = ''
            mock_data_file_path = f"mock_data/{req.env['REQUEST_METHOD'].lower()}{req.env['PATH_INFO']}.json"

            if os.path.exists(mock_data_file_path):
                self._logger.info('Returning data from %s', mock_data_file_path)
                with(open(mock_data_file_path)) as f:
                    body = f.read()
                raise falcon.http_status.HTTPStatus(falcon.HTTP_OK, body=body)
            else:
                self._logger.info('Mock data file: %s not found', mock_data_file_path)
                raise falcon.http_status.HTTPStatus(falcon.HTTP_NOT_FOUND)


class Context(object):
    pass


# Route requests into the Lambda function code path to simulate incoming events from AWS API Gateway.
class RequestRouter(object):

    def __init__(self, api_config, router_module, logger):
        self._api_config = api_config
        self._logger = logger
        self._router_module = router_module

    def set_response(self, req, resp):
        context = Context()
        context.api_config = self._api_config
        params = dict(
            event=dict(
                requestContext=dict(
                    http=dict(
                        method=req.method,
                        path=req.path
                    )
                )
            ),
            context=context,
            logger=self._logger
        )

        # API Gateway will omit the 'queryStringParameters' key in the event object if there are no
        # upstream query parameters.
        if req.params:
            params['event']['queryStringParameters'] = req.params

        # API Gateway will omit the 'body' param in the event for HTTP methods for which it does not pertain
        if hasattr(req.context, 'data') and req.context.data:
            params['event']['body'] = req.context.data

        result = self._router_module.handler(**params)
        resp.body = result.get('body', '')
        resp.status = (getattr(falcon, f"HTTP_{result.get('statusCode')}")
                       if result.get('statusCode') else falcon.HTTP_OK)

    # noinspection PyUnusedLocal
    def on_delete(self, req, resp):
        self.set_response(req, resp)

    # noinspection PyUnusedLocal
    def on_get(self, req, resp):
        self.set_response(req, resp)

    # noinspection PyUnusedLocal
    def on_post(self, req, resp):
        self.set_response(req, resp)

    # noinspection PyUnusedLocal
    def on_put(self, req, resp):
        self.set_response(req, resp)


class RequestHandler(object):

    @staticmethod
    def handle(api_responder, api_config, event, context, logger):
        # Enable only in case of temporary / emergency debugging in production.
        # This will leak secrets to CloudWatch Logs!
        # logger.debug('Event: %s', event)
        logger = loggers.assure_logger(logger)

        # absorb the API configuration into the top-level context object for convenience
        for key, value in api_config.items():
            setattr(context, key, value)

        http_method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
        params = event.get('queryStringParameters', {})

        logger.info('Processing %s %s', http_method, path)
        module_name = f"endpoints.{path.replace('/api/', '').replace('/', '.')}"

        logger.debug('Using module: %s to route request for path: %s', module_name, path)
        module = importlib.import_module(module_name)
        function = getattr(module, http_method.lower())

        body = event.get('body')

        if body:
            try:
                body = json.loads(body)

            # if the body cannot be JSON decoded, don't pass it on
            except json.JSONDecodeError:
                logger.error('Could not JSON decode request body:')
                logger.debug(body)
                body = None

        return api_responder.respond(function, params, body, context, logger)
