from http import HTTPStatus
from flask import jsonify, make_response
import logging
logger = logging.getLogger('heymans')

def not_found(msg='Not found'):
    return make_response(
        jsonify({'error': msg}), 
        HTTPStatus.NOT_FOUND
    )

def missing_file(msg='No file included in the upload'):
    return make_response(
        jsonify({'error': msg}),
         HTTPStatus.BAD_REQUEST
    )

def forbidden(msg="Forbidden"):
    return make_response(
        jsonify({'error': msg}),
        HTTPStatus.FORBIDDEN
    )

def unauthorized(msg="Unauthorized"):
    return make_response(
        jsonify({'error': msg}),
        HTTPStatus.UNAUTHORIZED
    )

def invalid_json(msg='JSON does not match expected pattern'):
    return make_response(
        jsonify({'error': msg}), 
        HTTPStatus.BAD_REQUEST
    )

def bad_request(msg='Bad request'):
    payload = msg if isinstance(msg, dict) else {'error': msg}
    return make_response(
        jsonify(payload),
        HTTPStatus.BAD_REQUEST
    )

def error(msg="Unspecified error"):
    logger.error(msg)
    return make_response(
        {'error': msg},
        HTTPStatus.BAD_REQUEST
    )

"""
The non-error helpers give differently formatted responses:
"""
def success(msg='success'):
    return make_response(
        jsonify({'message': msg}),
        HTTPStatus.OK
    )

def no_content():
    return make_response('', HTTPStatus.NO_CONTENT)
