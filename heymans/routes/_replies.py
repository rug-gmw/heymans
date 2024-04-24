from http import HTTPStatus
from flask import jsonify, make_response


def not_found(msg):
    return make_response(jsonify({'error': msg}), HTTPStatus.NOT_FOUND)
    
    
def forbidden(msg):
    return make_response(jsonify({'error': msg}), HTTPStatus.FORBIDDEN)


def no_content():
    return make_response('', HTTPStatus.NO_CONTENT)


def success(msg):
    return jsonify({'message': msg})
