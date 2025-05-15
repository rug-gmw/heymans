import json
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from . import invalid_json, missing_file, error, success, no_content, not_found
from .. import json_schemas
from ..database.operations import documents as ops

logger = logging.getLogger('heymans')
documents_api_blueprint = Blueprint('api/documents', __name__)


@documents_api_blueprint.route('/add', methods=['POST'])
@login_required
def add():
    """Add a new document with an associated file.

    Request
    -------
    Form Data:
        - json: JSON string with document metadata, e.g.:
            {
                "public": true
            }
        - file: File to be uploaded (multipart file)

    Returns
    -------
    200 OK
        JSON: {
            "document_id": <int>,
            "chunk_ids": [<int>, ...]
        }
    400 Bad Request
        If the input is invalid or file is missing.
    """
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
    """Update the public status of an existing document.

    Request JSON example
    --------------------
    {
        "document_id": <int>,
        "public": true
    }

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    400 Bad Request
        If the input is invalid.
    404 Not Found
        If the document does not exist or does not belong to the user.
    """
    try:
        validate(instance=request.json, schema=json_schemas.DOCUMENT_UPDATE)
    except ValidationError as e:
        return invalid_json()
    if ops.update_document(current_user.get_id(), request.json['document_id'],
                           request.json['public']):
        return success()
    return not_found('document does not exist or belongs to different user')


@documents_api_blueprint.route('/delete/<int:document_id>', methods=['DELETE'])
@login_required
def delete(document_id):
    """Delete an existing document by its identifier.

    Path Parameters
    ---------------
    document_id : int
        Identifier of the document to delete.

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    404 Not Found
        If the document does not exist or does not belong to the user.
    """
    if ops.delete_document(current_user.get_id(), document_id):
        return success()
    return not_found('document does not exist or belongs to different user')


@documents_api_blueprint.route('/list/<int:include_public>')
@login_required
def list_(include_public):
    """List all documents belonging to the user, optionally including public documents from other users.

    Path Parameters
    ---------------
    include_public : int
        0 to return only user's own documents;
        1 to include all public documents from other users.

    Returns
    -------
    200 OK
        JSON: [
            {
                "document_id": <int>,
                "filename": <str>,
                "public": <bool>,
                ...
            },
            ...
        ]
    """
    return jsonify(ops.list_documents(current_user.get_id(), include_public))
