import json
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from . import missing_file, error, success, not_found
from ..database.operations import documents as ops

logger = logging.getLogger('heymans')
documents_api_blueprint = Blueprint('api/documents', __name__)


@documents_api_blueprint.route('/add', methods=['POST'])
@login_required
def add():
    """Add a new document with an associated file. This expects multipart form
    data consistting of a single file and JSON data. If no name is specified, 
    the file name is used.

    Request JSON Example
    --------------------
    {
        "public": <bool>,
        "name": <str>    # optional
    }
    
    Reply JSON Example
    ------------------
    {
        "document_id": <int>,
        "chunk_ids": [<int>, ...]
    }

    Returns
    -------
    200 OK
    400 Bad Request
    """
    document_info = json.loads(request.form.get('json', ''))
    if 'file' not in request.files:
        return missing_file()
    file = request.files['file']
    public = document_info.get('public')
    filename = file.filename
    file_content = file.read()
    mimetype = file.content_type
    name = document_info.get('name', filename)
    try:
        document_id, chunk_ids = ops.add_document(
            current_user.get_id(), public, name, file_content, filename,
            mimetype)
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        return error(str(e))
    logger.info(f'Added document: {document_id}')
    return jsonify({'document_id': document_id, 'chunk_ids': chunk_ids})


@documents_api_blueprint.route('/update/<int:document_id>', methods=['POST'])
@login_required
def update(document_id):
    """Update the public status and/ or name of an existing document.

    Request JSON example
    --------------------
    {
        "public": <bool>,    # optional
        "name": <str>        # optional
    }

    Returns
    -------
    200 OK
    400 Bad Request
    404 Not Found
    """
    public = request.json.get('public')
    name = request.json.get('name')
    if ops.update_document(current_user.get_id(), document_id, public, name):
        return success()
    return not_found('document does not exist or belongs to different user')


@documents_api_blueprint.route('/delete/<int:document_id>', methods=['DELETE'])
@login_required
def delete(document_id):
    """Delete an existing document by its identifier.

    Returns
    -------
    200 OK
    404 Not Found
    """
    if ops.delete_document(current_user.get_id(), document_id):
        return success()
    return not_found('document does not exist or belongs to different user')


@documents_api_blueprint.route('/list/<int:include_public>')
@login_required
def list_(include_public):
    """List all documents belonging to the user, optionally including public
    documents from other users. Chunks are not included in the response, and
    should be retrieved using the `get` endpoint.

    Path Parameters
    ---------------
    include_public : int
        0 to return only user's own documents;
        1 to include all public documents from other users.
        
    Reply JSON Example
    ------------------
    [
        {
            "document_id": <int>,
            "name": <str>,
            "public": <bool>,
        },
        ...
    ]

    Returns
    -------
    200 OK
    """
    return jsonify(ops.list_documents(current_user.get_id(), include_public))
    
    
@documents_api_blueprint.route('/get/<int:document_id>')
@login_required
def get(document_id):
    """Get a document by its identifier.

    Reply JSON Example
    ------------------
    {
        "document_id": <int>,
        "name": <str>,
        "public": <bool>,
        "chunks": [
            {
                "chunk_id": <int>,
                "text": <str>,
                "embedding": <list[float]>,
            },
            ...
        ]
    }

    Returns
    -------
    200 OK
    404 Not Found
    """
    document = ops.get_document(current_user.get_id(), document_id)
    if document is None:
        return not_found('document does not exist or belongs to different user')
    return jsonify(document)
