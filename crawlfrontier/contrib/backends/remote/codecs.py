# -*- coding: utf-8 -*-
from crawlfrontier.core.models import Request
import json

def _prepare_request_message(request):
    return {'url': request.url,
            'method': request.method,
            'headers': request.headers,
            'cookies': request.cookies,
            'meta': request.meta}

def _prepare_links_message(links):
    return [_prepare_request_message(link) for link in links]

def _prepare_response_message(response):
    return {'url': response.url,
            'status_code': response.status_code,
            'meta': response.meta}


class CrawlFrontierJSONEncoder(json.JSONEncoder):
    def __init__(self, request_model, *a, **kw):
        self._request_model = request_model
        super(CrawlFrontierJSONEncoder, self).__init__(*a, **kw)

    def default(self, o):
        if isinstance(o, self._request_model):
            return _prepare_request_message(o)
        else:
            return super(CrawlFrontierJSONEncoder, self).default(o)


class KafkaJSONEncoder(CrawlFrontierJSONEncoder):
    def __init__(self, request_model, *a, **kw):
        super(KafkaJSONEncoder, self).__init__(request_model, *a, **kw)

    def encode_add_seeds(self, seeds):
        """
        Encodes add_seeds message

        :param list seeds A list of frontier Request objects
        :return bytes encoded message
        """
        return self.encode({
            'type': 'add_seeds',
            'seeds': [_prepare_request_message(seed) for seed in seeds]
        })

    def encode_page_crawled(self, response, links):
        """
        Encodes a page_crawled message

        :param object response A frontier Response object
        :param list links A list of Request objects

        :return bytes encoded message
        """
        return self.encode({
            'type': 'page_crawled',
            'r': _prepare_response_message(response),
            'links': _prepare_links_message(links)
        })

    def encode_request_error(self, request, error):
        """
        Encodes a request_error message
        :param object request A frontier Request object
        :param string error Error description

        :return bytes encoded message
        """
        return self.encode({
            'type': 'request_error',
            'r': _prepare_request_message(request),
            'error': error
        })

    def encode_request(self, request):
        return self.encode(_prepare_request_message(request))

    def encode_update_score(self, fingerprint, score):
        return self.encode({'type': 'update_score',
                            'fprint': fingerprint,
                            'score': score})


class KafkaJSONDecoder(json.JSONDecoder):
    def __init__(self, request_model, response_model, *a, **kw):
        self._request_model = request_model
        self._response_model = response_model
        super(KafkaJSONDecoder, self).__init__(*a, **kw)

    def _response_from_object(self, obj):
        request = self._request_model(url=obj['url'],
                                      meta=obj['meta'])
        return self._response_model(url=obj['url'],
                     status_code=obj['status_code'],
                     request=request)

    def _request_from_object(self, obj):
        return self._request_model(url=obj['url'],
                                   method=obj['method'],
                                   headers=obj['headers'],
                                   cookies=obj['cookies'],
                                   meta=obj['meta'])
    def decode(self, message):
        """
        Decodes the message

        :param bytes message encoded message
        :return tuple of message type and related objects
        """
        message = super(KafkaJSONDecoder, self).decode(message)
        if message['type'] == 'add_seeds':
            seeds = []
            for seed in message['seeds']:
                request = self._request_from_object(seed)
                seeds.append(request)
            return ('add_seeds', seeds)

        if message['type'] == 'page_crawled':
            response = self._response_from_object(message['r'])
            links = [self._request_from_object(link) for link in message['links']]
            return ('page_crawled', response, links)

        if message['type'] == 'request_error':
            request = self._request_from_object(message['r'])
            return ('request_error', request, message['error'])

        if message['type'] == 'update_score':
            return ('update_score', message['fprint'], message['score'])
        return TypeError('Unknown message type')

    def decode_request(self, message):
        obj = super(KafkaJSONDecoder, self).decode(message)
        return self._request_model(url=obj['url'],
                                    method=obj['method'],
                                    headers=obj['headers'],
                                    cookies=obj['cookies'],
                                    meta=obj['meta'])

