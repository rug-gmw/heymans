import json
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from . import invalid_json, missing_file, error, success, no_content
from .. import json_schemas
from ..database.operations import documents as ops

logger = logging.getLogger('heymans')
documents_api_blueprint = Blueprint('api/documents', __name__)


@documents_api_blueprint.route('/add', methods=['POST'])
@login_required
def add():
    document_info = json.loads(request.form.get('json', ''))
    try:
        validate(instance=document_info, schema=json_schemas.DOCUMENT)
    except ValidationError as e:
        return invalid_json()
    if 'file' not in request.files:
        return missing_file()
    file = request.files['file']
    public = document_info['public']
    filename = file.filename
    file_content = file.read()
    mimetype = file.content_type
    try:
        document_id, chunk_ids = ops.add_document(
            current_user.get_id(), public, file_content, filename, mimetype)
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        return error(str(e))
    logger.info(f'Added document: {document_id}')
    return jsonify({'document_id': document_id, 'chunk_ids': chunk_ids})


@documents_api_blueprint.route('/update', methods=['POST'])
@login_required
def update():
    try:
        validate(instance=request.json, schema=json_schemas.DOCUMENT_UPDATE)
    except ValidationError as e:
        return invalid_json()
    if ops.update_document(current_user.get_id(), request.json['document_id'],
                           request.json['public']):
        return no_content()
    return error('document does not exist or belongs to different user')


@documents_api_blueprint.route('/delete/<int:document_id>', methods=['DELETE'])
@login_required
def delete(document_id):
    if ops.delete_document(current_user.get_id(), document_id):
        return no_content()
    return error('document does not exist or belongs to different user')


@documents_api_blueprint.route('/list/<int:include_public>')
@login_required
def list_(include_public):
    return jsonify(ops.list_documents(current_user.get_id(), include_public))
