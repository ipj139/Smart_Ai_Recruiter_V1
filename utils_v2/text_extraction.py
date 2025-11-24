"""
Text extraction utilities for PDF, DOCX, and DOC files
"""
import streamlit as st
import tempfile
import os
import re
from pdfminer.high_level import extract_text
from pypdf import PdfReader
import docx2txt
import olefile


def extract_pdf_text(uploaded_file):
    """Extract text from PDF file"""
    # First try pdfminer
    try:
        extracted_text = extract_text(uploaded_file) or ""
        if extracted_text and extracted_text.strip():
            return extracted_text
    except Exception:
        # Silently fall back to PyPDF without displaying a warning in the UI
        pass
    # Fallback to pypdf
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        pages_text = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            pages_text.append(page_text)
        combined = "\n".join(pages_text)
        return combined
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return ""


def extract_docx_text(uploaded_file):
    """Extract text from DOCX file
    Supports both Streamlit uploaded files and regular file objects/file paths
    """
    try:
        # Check if it's a file path (string)
        if isinstance(uploaded_file, str):
            if os.path.exists(uploaded_file):
                extracted_text = docx2txt.process(uploaded_file) or ""
                return extracted_text
            else:
                return ""
        
        # Check if it's a Streamlit uploaded file (has getbuffer method)
        if hasattr(uploaded_file, 'getbuffer'):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name
            try:
                extracted_text = docx2txt.process(tmp_path) or ""
                return extracted_text
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        else:
            # Regular file object - read content and write to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                if hasattr(uploaded_file, 'read'):
                    # File object - read and write
                    uploaded_file.seek(0)  # Reset file pointer
                    tmp.write(uploaded_file.read())
                else:
                    return ""
                tmp_path = tmp.name
            try:
                extracted_text = docx2txt.process(tmp_path) or ""
                return extracted_text
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    except Exception as e:
        if 'st' in globals():
            st.error(f"Error extracting text from DOCX: {str(e)}")
        return ""


def extract_doc_text(uploaded_file):
    """
    Extract text from legacy .doc files using olefile (Python 3.12 compatible).
    This replaces textract which has compatibility issues with Python 3.12.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name
        try:
            # Check if file is a valid OLE file
            if not olefile.isOleFile(tmp_path):
                # If not OLE format, try reading as binary and extract text
                with open(tmp_path, 'rb') as f:
                    content = f.read()
                # Try to extract readable text from binary content
                # This regex pattern extracts sequences of printable ASCII characters
                text_pattern = re.compile(rb'[\x20-\x7E]{3,}')
                matches = text_pattern.findall(content)
                extracted_text = b' '.join(matches).decode('utf-8', errors='ignore')
                # Clean up excessive whitespace
                extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()
                if extracted_text:
                    return extracted_text
                return ""
            
            # Open OLE file
            ole = olefile.OleFileIO(tmp_path)
            
            # Try to read WordDocument stream (standard stream in .doc files)
            extracted_text = ""
            try:
                if ole.exists('WordDocument'):
                    stream = ole.openstream('WordDocument')
                    content = stream.read()
                    stream.close()
                    
                    # Extract readable text from binary content
                    # Method 1: Extract sequences of printable ASCII characters
                    text_pattern = re.compile(rb'[\x20-\x7E]{3,}')
                    matches = text_pattern.findall(content)
                    extracted_text = b' '.join(matches).decode('utf-8', errors='ignore')
                    
                    # Clean up excessive whitespace and control characters
                    extracted_text = re.sub(r'\s+', ' ', extracted_text)
                    extracted_text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', extracted_text)
                    extracted_text = extracted_text.strip()
                    
                    # If we got meaningful text, return it
                    if len(extracted_text) > 10:  # Minimum meaningful length
                        return extracted_text
            except Exception:
                pass
            
            # Fallback: Try to extract text from all streams
            try:
                all_text_parts = []
                for stream_name in ole.listdir():
                    if stream_name and isinstance(stream_name, tuple):
                        stream_name = stream_name[0] if len(stream_name) > 0 else None
                    if stream_name:
                        try:
                            stream = ole.openstream(stream_name)
                            content = stream.read()
                            stream.close()
                            
                            # Extract readable text
                            text_pattern = re.compile(rb'[\x20-\x7E]{4,}')
                            matches = text_pattern.findall(content)
                            text_part = b' '.join(matches).decode('utf-8', errors='ignore')
                            text_part = re.sub(r'\s+', ' ', text_part).strip()
                            
                            if len(text_part) > 10:
                                all_text_parts.append(text_part)
                        except Exception:
                            continue
                
                if all_text_parts:
                    extracted_text = ' '.join(all_text_parts)
                    extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()
                    if extracted_text:
                        return extracted_text
            except Exception:
                pass
            
            ole.close()
            
            # Final fallback: Read file as binary and extract text
            with open(tmp_path, 'rb') as f:
                content = f.read()
            text_pattern = re.compile(rb'[\x20-\x7E]{4,}')
            matches = text_pattern.findall(content)
            extracted_text = b' '.join(matches).decode('utf-8', errors='ignore')
            extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()
            
            return extracted_text if extracted_text else ""
            
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        st.error(f"Error extracting text from DOC: {str(e)}")
        return ""


def extract_resume_text(uploaded_file):
    """Router to choose the right extractor based on file extension"""
    filename = (uploaded_file.name or "").lower()
    if filename.endswith(".pdf"):
        return extract_pdf_text(uploaded_file)
    if filename.endswith(".docx"):
        return extract_docx_text(uploaded_file)
    if filename.endswith(".doc"):
        return extract_doc_text(uploaded_file)
    st.error("Unsupported file type. Please upload a PDF, DOC, or DOCX file.")
    return ""


def extract_jd_text(uploaded_file):
    """Function to extract text from JD documents (reuse existing extractors)"""
    filename = (uploaded_file.name or "").lower()
    if filename.endswith(".pdf"):
        return extract_pdf_text(uploaded_file)
    if filename.endswith(".docx"):
        return extract_docx_text(uploaded_file)
    if filename.endswith(".doc"):
        return extract_doc_text(uploaded_file)
    if filename.endswith(".txt"):
        try:
            # For text files, decode directly
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            st.error(f"Error reading text file: {str(e)}")
            return ""
    st.error("Unsupported JD file type. Please upload a PDF, DOC, DOCX, or TXT file.")
    return ""

