from http import HTTPStatus
from flask import jsonify, make_response
import logging
logger = logging.getLogger('heymans')


def not_found(msg):
    return make_response(jsonify({'error': msg}), HTTPStatus.NOT_FOUND)
    
    
def missing_file():
    return make_response(jsonify({'error': 'no file part in post data'}),
                         HTTPStatus.BAD_REQUEST)

    
def forbidden(msg):
    return make_response(jsonify({'error': msg}), HTTPStatus.FORBIDDEN)


def no_content():
    return make_response('', HTTPStatus.NO_CONTENT)
    
    
def invalid_json():
    return make_response('JSON does not match schema', HTTPStatus.BAD_REQUEST)
    
    
def error(msg):
    logger.error(msg)
    return make_response({'error': msg}, HTTPStatus.BAD_REQUEST)


def success(msg='success'):
    return jsonify({'message': msg})
