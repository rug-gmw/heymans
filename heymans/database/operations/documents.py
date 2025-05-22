import logging
import tempfile
import pypandoc
from pathlib import Path
from ..models import db, Document, Chunk
from ..schemas import DocumentSchema
from ... import config

logger = logging.getLogger('heymans')


def add_document(user_id: int, public: bool, name: str, content: bytes,
                 filename: str, mimetype: str) -> list:
    logger.info(f'adding document with mimetype {mimetype}')
    ext = Path(filename).suffix
    if mimetype.startswith('text/'):
        txt_content = content
    else:
        # Convert bytes content to a tempfile, then to plain text
        with tempfile.NamedTemporaryFile(
                delete=False, suffix=f'.{ext}') as temp:
            temp.write(content)
            logger.info(f'creating temporary file {temp.name}')
            temp_path = Path(temp.name)
        # Use pandoc to convert the file to text and then remove the tempfile
        txt_content = pypandoc.convert_file(str(temp_path), 'plain')
        temp_path.unlink()

    # Split text content into chunks of max 10,000 characters
    chunk_size = config.document_max_chunk_size
    chunks = [txt_content[i:i + chunk_size]
              for i in range(0, len(txt_content), chunk_size)]
    logger.info(f'document split into {len(chunks)} chunks')

    # Create the DB objects in one transaction
    with db.session.begin():
        document = Document(user_id=user_id, public=public, name=name)
        db.session.add(document)
        db.session.flush()  # so we have document.document_id

        chunk_ids = []
        for chunk_content in chunks:
            chunk = Chunk(document_id=document.document_id,
                          content=chunk_content)
            db.session.add(chunk)
            db.session.flush()       # obtain chunk_id
            chunk_ids.append(chunk.chunk_id)
        document_id = document.document_id
    # after `with db.session.begin()` the transaction is committed
    return [document_id, chunk_ids]


def update_document(user_id: int, document_id: int, public: bool | None,
                    name: str | None) -> bool:
    """Updates the public status and/ or name of the document. Returns False if
    the doc doesn’t exist or doesn’t belong to the user."""
    with db.session.begin():
        document = db.session.query(Document).filter_by(
            document_id=document_id, user_id=user_id).one_or_none()
        if document is None:
            logger.debug("update_document: document %s not found for user %s",
                         document_id, user_id)
            return False
        if public is not None:
            document.public = public
        if name is not None:
            document.name = name
        # commit automatic on context-exit
    return True


def delete_document(user_id: int, document_id: int) -> bool:
    """Delete a document and its chunks. Returns False on permission / missing."""
    with db.session.begin():
        document = db.session.query(Document).filter_by(
            document_id=document_id, user_id=user_id).one_or_none()

        if document is None:
            logger.debug("delete_document: document %s not found for user %s",
                         document_id, user_id)
            return False

        db.session.query(Chunk).filter_by(document_id=document_id).delete()
        db.session.delete(document)
    return True


def list_documents(user_id: int, include_public: bool) -> list:
    """Return the user’s own documents plus, optionally, public ones."""
    with db.session.begin():             # read-only transaction
        query = db.session.query(Document).filter_by(user_id=user_id)
        if include_public:
            public_documents_query = db.session.query(Document).filter_by(
                public=True)
            query = query.union(public_documents_query).distinct()

        documents = query.all()
        document_schema = DocumentSchema(many=True)
        return document_schema.dump(documents)


def has_access(user_id: int, document_id: int) -> bool:
    """Return True if the user is allowed to view/use the given document.

    A user has access when:
    1. The document exists, and
    2. The document is public      OR
       The user is the owner of the document.
    """
    # Wrap the read in its own (read-only) transaction so we don't leave the
    # session in a "transaction in progress" state.
    with db.session.begin():  # auto-rollback on exit if nothing is dirty
        document = db.session.query(Document).filter_by(
            document_id=document_id
        ).one_or_none()

        if document is None:
            logger.debug(f"Document {document_id} not found — access denied.")
            return False
    
        access_granted = document.public or (document.user_id == user_id)
        logger.debug(
            "Access check for user=%s, document=%s: public=%s, owner=%s → %s",
            user_id, document_id, document.public, document.user_id, access_granted
        )
    return access_granted