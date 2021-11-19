import logging
import os
from wsgiref import simple_server

import falcon
from madeira_utils import loggers
from madeira_utils import utils


class FalconApiDev(object):

    def __init__(self, router_module):
        # Development API always loads with debug logging enabled!
        self._logger = loggers.get_logger(level=logging.DEBUG)

        self._logger.info('Loading API configuration from filesystem')
        api_config = utils.load_yaml('config.yaml')

        if not api_config.get('test'):
            raise RuntimeError("Could not load API configuration")

        self._request_router = RequestRouter(
            api_config['test'], router_module, self._logger)

        self._logger.info(f'Initializing API using falcon {falcon.__version__}')
        self.api = falcon.App(middleware=[
            CorsPreflight(self._logger),
            MockDataResponse(self._logger),
            FormatResponse(self._logger)
        ])

        for route in api_config['routes']:
            self.api.add_route(route, self._request_router)

        self._logger.info('API Initialized')

    def serve_wsgi(self):
        """Serve the API using the `wsgiref.simple_server` implementation.

        NOTE: this does not provide an "auto reloading" function the way that more robust WSGI
            servers (Werkzeug, gunicorn, etc) can.
        """
        webserver_bind_address = '127.0.0.1'
        webserver_port = 8080
        self._logger.debug(
            'Launching webserver bound to %s:%s',
            webserver_bind_address,
            webserver_port
        )
        httpd = simple_server.make_server(
            webserver_bind_address,
            webserver_port,
            self.api
        )
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
        req.context.data = req.stream.read(req.content_length or 0).decode('utf-8')

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
            mock_data_file_path = (
                f"mock_data/{req.env['REQUEST_METHOD'].lower()}{req.env['PATH_INFO']}.json"
            )

            if os.path.exists(mock_data_file_path):
                self._logger.info('Returning data from %s', mock_data_file_path)
                with(open(mock_data_file_path)) as f:
                    body = f.read()
                raise falcon.http_status.HTTPStatus(falcon.HTTP_OK, text=body)
            else:
                self._logger.info('Mock data file: %s not found', mock_data_file_path)
                raise falcon.http_status.HTTPStatus(falcon.HTTP_NOT_FOUND)


class Context(object):
    pass


# Route requests into the Lambda function code path to simulate incoming events from AWS API
# Gateway.
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
                headers={k.title(): v for k, v in req.headers.items()},
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

        # API Gateway will omit the 'body' param in the event for HTTP methods for which it does
        # not pertain
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
