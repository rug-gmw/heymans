import logging
import tempfile
import pypandoc
from pathlib import Path
from ..models import db, Document, Chunk
from ..schemas import DocumentSchema
from ... import config

logger = logging.getLogger('heymans')


def add_document(user_id: int, public: bool, content: bytes, filename: str,
                 mimetype: str) -> list:
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
    # Create document entry
    document = Document(user_id=user_id, public=public)
    db.session.add(document)
    db.session.flush()
    # Create chunk entries
    chunk_ids = []
    for chunk_content in chunks:
        chunk = Chunk(document_id=document.document_id, content=chunk_content)
        db.session.add(chunk)
        db.session.flush()
        chunk_ids.append(chunk.chunk_id)
    db.session.commit()
    return [document.document_id, chunk_ids]


def update_document(user_id: int, document_id: int, public: bool) -> bool:
    document = db.session.query(Document).filter_by(
        document_id=document_id, user_id=user_id).one_or_none()
    if document is None:
        return False
    document.public = public
    db.session.commit()
    return True


def delete_document(user_id: int, document_id: int) -> bool:
    document = db.session.query(Document).filter_by(
        document_id=document_id, user_id=user_id).one_or_none()
    if document is None:
        return False
    db.session.query(Chunk).filter_by(document_id=document_id).delete()
    db.session.delete(document)
    db.session.commit()
    return True


def list_documents(user_id: int, include_public: bool) -> list:
    query = db.session.query(Document).filter_by(user_id=user_id)
    if include_public:
        public_documents_query = db.session.query(Document).filter_by(
            public=True)
        query = query.union(public_documents_query).distinct()
    documents = query.all()
    document_schema = DocumentSchema(many=True)
    return document_schema.dump(documents)
