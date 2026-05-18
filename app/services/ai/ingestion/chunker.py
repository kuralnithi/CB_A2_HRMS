"""
Hierarchical chunker using Docling.
Adapted from the reference project.
"""
import uuid
import logging
from pydantic import BaseModel
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)

class ChunkMetadata(BaseModel):
    chunk_id: str
    source_document: str
    collection: str
    access_roles: List[str]
    section_title: str
    page_number: int
    chunk_type: str
    parent_chunk_id: Optional[str]
    hierarchy_path: List[str]
    parent_summary: str

def create_chunks(
    filepath: str,
    original_filename: str,
    collection: str,
    access_roles: list[str],
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> list[dict]:
    """
    Parse a document with Docling and create hierarchical chunks.
    """
    chunks = []

    try:
        # CASE 1: Handle CSV-converted files with a fast row-based chunker
        if original_filename.lower().endswith(".csv"):
            logger.info(f"Using fast CSV chunker for {original_filename}")
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            header_line = lines[2] if len(lines) > 2 else ""
            sep_line = lines[3] if len(lines) > 3 else ""
            data_lines = lines[4:] if len(lines) > 4 else []
            
            if data_lines:
                rows_per_chunk = 15
                for j in range(0, len(data_lines), rows_per_chunk):
                    batch = data_lines[j:j + rows_per_chunk]
                    chunk_text = f"{lines[0]}\n{header_line}{sep_line}" + "".join(batch)
                    
                    metadata = ChunkMetadata(
                        chunk_id=str(uuid.uuid4()),
                        source_document=original_filename,
                        collection=collection,
                        access_roles=access_roles,
                        section_title=f"Page {j // rows_per_chunk + 1}",
                        page_number=j // rows_per_chunk + 1,
                        chunk_type="table",
                        parent_chunk_id=None,
                        hierarchy_path=[original_filename],
                        parent_summary="",
                    )
                    chunks.append({"text": chunk_text, "metadata": metadata})
                
                return chunks

        # CASE 2: Standard Docling hierarchical chunking
        logger.info(f"Parsing {original_filename} with Docling...")
        
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling_core.transforms.chunker import HierarchicalChunker
        
        pipeline_options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=False,
        )
        
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = converter.convert(filepath)
        doc = result.document

        chunker = HierarchicalChunker(
            max_tokens=512,
            overlap=50,
        )
        doc_chunks = list(chunker.chunk(doc))
        
        doc_parent_id = str(uuid.uuid4())
        
        total_chunks = len(doc_chunks)
        if progress_callback:
            progress_callback(30, f"Chunking {total_chunks} segments...")

        for i, chunk in enumerate(doc_chunks):
            if progress_callback and i % 5 == 0:
                # scale progress from 30 to 80 based on chunks processed
                current_prog = 30 + int(50 * (i / max(1, total_chunks)))
                progress_callback(current_prog, f"Processing chunk {i+1} of {total_chunks}...")
                
            chunk_id = str(uuid.uuid4())
            chunk_text = chunk.text if hasattr(chunk, "text") else str(chunk)

            if not chunk_text.strip():
                continue

            section_title = ""
            page_number = 0
            chunk_type = "text"
            hierarchy_path = [original_filename]
            parent_chunk_id = doc_parent_id

            if hasattr(chunk, "meta"):
                meta = chunk.meta
                if hasattr(meta, "headings") and meta.headings:
                    section_title = meta.headings[-1] if meta.headings else ""
                    hierarchy_path.extend(meta.headings)
                if hasattr(meta, "page"):
                    page_number = meta.page or 0
                if hasattr(meta, "doc_items") and meta.doc_items:
                    for item in meta.doc_items:
                        label = getattr(item, "label", "")
                        if label:
                            label_lower = str(label).lower()
                            if "table" in label_lower:
                                chunk_type = "table"
                            elif "code" in label_lower:
                                chunk_type = "code"
                            elif "head" in label_lower or "title" in label_lower:
                                chunk_type = "heading"
                        if hasattr(item, "prov") and item.prov:
                            for prov in item.prov:
                                if hasattr(prov, "page_no"):
                                    page_number = prov.page_no or page_number

            metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source_document=original_filename,
                collection=collection,
                access_roles=access_roles,
                section_title=section_title,
                page_number=page_number,
                chunk_type=chunk_type,
                parent_chunk_id=parent_chunk_id,
                hierarchy_path=hierarchy_path,
                parent_summary="",
            )

            chunks.append({
                "text": chunk_text,
                "metadata": metadata,
            })

    except Exception as e:
        logger.error(f"Error chunking {original_filename}: {e}", exc_info=True)
        # Fallback text chunking
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            if text.strip():
                chunk_id = str(uuid.uuid4())
                metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    source_document=original_filename,
                    collection=collection,
                    access_roles=access_roles,
                    section_title="Full Document",
                    page_number=1,
                    chunk_type="text",
                    parent_chunk_id=None,
                    hierarchy_path=[original_filename],
                    parent_summary="",
                )
                max_chars = 2000
                for j in range(0, len(text), max_chars):
                    sub_text = text[j:j + max_chars]
                    sub_id = str(uuid.uuid4())
                    sub_meta = metadata.model_copy(update={"chunk_id": sub_id})
                    chunks.append({"text": sub_text, "metadata": sub_meta})
        except Exception as fallback_err:
            logger.error(f"Fallback chunking failed for {original_filename}: {fallback_err}")

    return chunks
