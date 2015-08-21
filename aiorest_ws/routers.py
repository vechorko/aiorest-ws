# -*- coding: utf-8 -*-
"""
    This modules provide a functions and classes, which every developer
    can used for determine URL for their APIs.

    For example, we can use this features something like this:

        router = SimpleRouter()
        router.register('user/info', info_handler, methods='GET')
        router.register('user/register', register_handler, methods='POST')
        router.register('user/profile/{user_name}', user_handler,
                        methods=['GET', 'PUT'])
"""
__all__ = ('SimpleRouter', )


from .abstract import AbstractEndpoint, AbstractRouter
from .exceptions import BaseAPIException, EndpointValueError, \
    NotSpecifiedHandler, NotSpecifiedURL
from .log import logger
from .serializers import JSONSerializer
from .parsers import URLParser
from .validators import RouteArgumentsValidator
from .wrappers import Response


class SimpleRouter(AbstractRouter):
    """Default router class, used for working with REST over WebSockets."""
    args_validator = RouteArgumentsValidator()
    url_parser = URLParser()

    def __init__(self, *args, **kwargs):
        super(SimpleRouter, self).__init__()
        self._urls = []
        self._routes = {}

    def _correct_path(self, path):
        """Convert path to valid value.

        :param path: URL, which used to get access to API.
        """
        path = path.strip()
        if not path.endswith('/'):
            path = path + '/'
        return path

    def register(self, path, handler, methods, name=None):
        """Add new endpoint to the router.

        :param path: URL, which used to get access to API.
        :param handler: inherited class from the MethodBasedView, which used
                        for processing request.
        :param methods: list of available for user methods or string with
                        concrete method name.
        :param name: short name for endpoint.
        """
        path = self._correct_path(path)
        self.args_validator.validate(path, handler, methods, name)

        route = self.url_parser.define_route(path, handler, methods, name)
        self._register_url(route)

    def register_endpoint(self, endpoint):
        """Add new endpoint to the router.

        :param endpoint: function with @endpoint decorator, which used for
                         processing request.
        """
        path, handler, methods, name = endpoint()
        self.register(path, handler, methods, name)

    def extract_url(self, request):
        """Extracting URL parameter for request.

        :param request: request from the user.
        """
        if not request.url:
            raise NotSpecifiedURL()
        return self._correct_path(request.url)

    def search_handler(self, request, url):
        """Searching handler by URL.

        :param request: request from user.
        :param url: path to the registered endpoint.
        """
        args = ()
        kwargs = {}
        handler = None
        for route in self._urls:
            match = route.match(url)
            if match is not None:
                handler = route.handler()
                args = match
                params = request.args
                if params:
                    kwargs.update({'params': params})
                break
        return handler, args, kwargs

    def process_request(self, request):
        """Handle received request from user.

        :param request: request from user.
        """
        logger.info("\"{method} {url}\" args={args}".format(
            method=request.method,
            url=request.url,
            args=request.args)
        )
        response = Response()

        try:
            url = self.extract_url(request)
            handler, args, kwargs = self.search_handler(request, url)

            for middleware in self.middlewares:
                request = middleware.process_request(request)

            # invoke handler for request
            if handler:
                # search serializer for response
                format = request.get_argument('format')
                serializer = handler.get_serializer(format, *args, **kwargs)

                response.content = handler.dispatch(request, *args, **kwargs)
                response.append_request(request)
            else:
                raise NotSpecifiedHandler()
        except BaseAPIException as exc:
            logger.exception(exc)
            response.content = {'details': exc.detail}
            serializer = JSONSerializer()

        return serializer.serialize(response.content)

    def _register_url(self, route):
        """Register new endpoint.

        :param route: instance of class, inherited from AbstractEndpoint.
        """
        if not issubclass(type(route), (AbstractEndpoint, )):
            raise TypeError(u"Custom route must be inherited from the "
                            u"AbstractEndpoint class.")

        name = route.name
        if name is not None:
            if name in self._routes.keys():
                raise EndpointValueError(
                    'Duplicate {}, already handled by {}'
                    .format(name, self._routes[name]))
            else:
                self._routes[name] = route
        self._urls.append(route)

    def include(self, router):
        """Appending endpoints from another router to self.

        :param router: instance of subclass, derived from AbstractRouter
        """
        if not issubclass(type(router), (SimpleRouter, )):
            raise TypeError(u"Passed router must be inherited from the "
                            u"SimpleRouter class.")
        self._urls.extend(router._urls)
        self._routes.update(router._routes)
