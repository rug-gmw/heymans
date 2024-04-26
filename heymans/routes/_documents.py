import json
from flask import Blueprint, request, jsonify
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from . import invalid_json, missing_file, error, success
from .. import json_schemas
from ..database.operations import documents as ops

logger = logging.getLogger('heymans')
documents_api_blueprint = Blueprint('api/documents', __name__)


@documents_api_blueprint.route('/add', methods=['POST'])
def add():
    document_info = json.loads(request.form.get('json', ''))
    try:
        validate(instance=document_info, schema=json_schemas.DOCUMENT)
    except ValidationError as e:
        return invalid_json()
    if 'file' not in request.files:
        return missing_file()
    file = request.files['file']
    user_id = document_info['user_id']
    public = document_info['public']
    filename = file.filename
    file_content = file.read()
    mimetype = file.content_type
    try:
        document_id, chunk_ids = ops.add_document(
            user_id, public, file_content, filename, mimetype)
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        return error(str(e))
    logger.info(f'Added document: {document_id}')
    return jsonify({'document_id': document_id, 'chunk_ids': chunk_ids})
