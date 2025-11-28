import time

from pydantic import BaseModel
import qdrant_client
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding, OpenAIEmbeddingModelType
from llama_index.llms.openai import OpenAI
from llama_index.core import (
    VectorStoreIndex,
    Document,
    Settings
)
from llama_index.core.query_engine import CitationQueryEngine
from dataclasses import dataclass
import os
import re
import glob
import pdfplumber

key = os.environ['OPENAI_API_KEY']

@dataclass
class Input:
    query: str
    file_path: str

@dataclass
class Citation:
    source: str
    text: str
    number: int | None = None

class Output(BaseModel):
    query: str
    response: str
    citations: list[Citation]

class DocumentService:

    """
    Update this service to load the pdf and extract its contents.
    The example code below will help with the data structured required
    when using the QdrantService.load() method below. Note: for this
    exercise, ignore the subtle difference between llama-index's 
    Document and Node classes (i.e, treat them as interchangeable).

    # example code
    def create_documents() -> list[Document]:

        docs = [
            Document(
                metadata={"Section": "Law 1"},
                text="Theft is punishable by hanging",
            ),
            Document(
                metadata={"Section": "Law 2"},
                text="Tax evasion is punishable by banishment.",
            ),
        ]

        return docs
    """
    def create_documents(self) -> list[Document]:
        """
        Parse PDF files in ./docs and produce Documents for each numbered section.
        - pdf_dir fixed to ./docs
        - look for bold text prefixed by section numbers for section titles
        - source is the first non-empty line that does NOT start with a section prefix
        - section detection via regex for numeric sections like 1, 1.1, 1.1.2
        - join wrapped lines into paragraphs and strip trailing citation blocks
        """
        curr_docs: list[Document] = []
        pdf_dir = os.path.join(os.getcwd(), "docs")
        pdf_paths = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))

        # Section pattern: captures numeric section (1, 1.1, 1.1.2...) and trailing text
        section_pattern = re.compile(r'^(?P<section>\d+(?:\.\d+)*)(?:[.)]\s*)?(?P<rest>.*)$')

        for pdf_path in pdf_paths:
            filename = os.path.basename(pdf_path)
            current_section = None
            section_title = None
            current_text_lines: list[str] = []
            bold_candidates = set()

            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    pages_text.append(page.extract_text() or "")
                    # collect bold-only text across pages
                    bold_filtered = page.filter(
                        lambda obj: obj.get("object_type") == "char" and "Bold" in obj.get("fontname", "")
                    )
                    bold_text = bold_filtered.extract_text() or ""
                    for bl in bold_text.splitlines():
                        bls = bl.strip()
                        if bls:
                            bold_candidates.add(bls)

                full_text = "\n".join(pages_text)

            lines = full_text.splitlines()

            # determine source: first line if not section else filename
            source = lines[0].strip() \
                if not section_pattern.match(lines[0].strip()) \
                else os.path.splitext(filename)[0]

            # iterate lines and split into section documents
            for line in lines:
                curr_line = line.rstrip()
                if not curr_line.strip():
                    # preserve paragraph break if inside a section
                    if current_section is not None:
                        current_text_lines.append("")
                    continue

                section_match = section_pattern.match(curr_line.strip())
                if section_match:
                    self.flush_section(curr_docs, current_section, current_text_lines, source, filename, section_title)

                    # start new section
                    current_section = section_match.group("section")
                    rest = section_match.group("rest").strip()

                    # If rest exactly matches a bold candidate or looks like a short title, treat as title
                    if curr_line.strip() in bold_candidates and self.looks_like_title(rest):
                        section_title = rest
                        current_text_lines = []
                    else:
                        current_text_lines = [rest] if rest else []
                    continue

                # normal body line: merge wraps into previous line when appropriate
                if current_section is not None:
                    if current_text_lines:
                        prev = current_text_lines[-1]
                        if self.should_join(prev, curr_line):
                            current_text_lines[-1] = prev.rstrip() + " " + curr_line.lstrip()
                        else:
                            current_text_lines.append(curr_line)
                    else:
                        current_text_lines.append(curr_line)

            # flush last section at EOF
            self.flush_section(curr_docs, current_section, current_text_lines, source, filename, section_title)

        return curr_docs

    def flush_section(self, curr_docs: list[Document], current_section: str, current_text_lines: list[str],
                      source: str, filename: str, section_title: str | None):
        if current_section is not None and any(t.strip() for t in current_text_lines):
            content_lines = self.strip_trailing_citations(current_text_lines)
            paragraphs = []
            para_buf = []
            for ln in content_lines:
                if ln == "":
                    if para_buf:
                        paragraphs.append(" ".join(para_buf).strip())
                        para_buf = []
                    continue
                if para_buf and self.should_join(para_buf[-1], ln):
                    para_buf[-1] = para_buf[-1].rstrip() + " " + ln.lstrip()
                else:
                    para_buf.append(ln)
            if para_buf:
                paragraphs.append(" ".join(para_buf).strip())
            doc_text = "\n\n".join(paragraphs).strip()
            if doc_text:
                metadata = {
                    "section": current_section,
                    "section_title": section_title or "",
                    "source": source,
                    "file_name": filename,
                }
                curr_docs.append(Document(metadata=metadata, text=doc_text))

    def looks_like_title(self, s: str) -> bool:
        """Heuristic: short, few words, starts with capital, not a full sentence."""
        if not s:
            return False
        s = s.strip()
        if len(s) > 60:
            return False
        if len(s.split()) > 8:
            return False
        if not re.match(r'^[A-Z0-9]', s):
            return False
        # avoid lines that look like full sentences
        if s.endswith('.') or s.endswith(':') or s.endswith(';'):
            return False
        return True

    def strip_trailing_citations(self, lines: list[str]) -> list[str]:
        """Remove trailing 'Citations:' block and subsequent URL lines."""
        if not lines:
            return lines
        # find the first index where a citations block or raw url begins
        for i, ln in enumerate(lines):
            s = ln.strip()
            if not s:
                continue
            if s.lower().startswith("citations"):
                return lines[:i]
            if re.match(r'https?://', s) or s.startswith('www.'):
                return lines[:i]
        return lines

    def should_join(self, prev: str, curr: str) -> bool:
        """Return True if curr is likely a continuation of prev (wrap)."""
        if not prev or not curr:
            return False
        # continuation if next line starts lowercase (common for wrapped lines)
        if curr[0].islower():
            return True
        # continuation if prev doesn't end with terminal punctuation
        if not prev.endswith(('.', '!', '?', '"', "'")):
            return True
        if not curr[0].isdigit() and not curr.lower().startswith("citations"):
            return True
        return False

class QdrantService:
    def __init__(self, k: int = 2):
        self.index = None
        self.k = k
        self.source_regex = re.compile(r'^\s*Source\s*(?P<number>\d+)\s*:\s*(?P<text>.+)$', re.IGNORECASE)
        self.query_template = (
            "You are a legal assistant helping users with questions about the laws in the provided documents "
            "regarding the laws of The Seven Kingdoms. Remember to answer based only on the context provided and cite "
            "only relevant sources. If the available legal documents do not contain the answer, please indicate "
            "so. Only include information relevant to the query in your response. The user query is:"
        )
    
    def connect(self) -> None:
        client = qdrant_client.QdrantClient(location=":memory:")
                
        vstore = QdrantVectorStore(client=client, collection_name='temp')

        Settings.embed_model = OpenAIEmbedding(
            model_name=OpenAIEmbeddingModelType.TEXT_EMBED_3_SMALL
        )
        Settings.llm = OpenAI(api_key=key, model="gpt-4o")

        self.index = VectorStoreIndex.from_vector_store(vector_store=vstore)

    def load(self, docs: list[Document]):
        self.index.insert_nodes(docs)

    def add_instructions(self, query_str: str) -> str:
        return self.query_template + "\n\n" + query_str
    
    def query(self, query_str: str) -> Output:

        """
        This method needs to initialize the query engine, run the query, and return
        the result as a pydantic Output class. This is what will be returned as
        JSON via the FastAPI endpount. Fee free to do this however you'd like, but
        it's worth noting that the llama-index package has a CitationQueryEngine...

        Also, be sure to make use of self.k (the number of vectors to return based
        on semantic similarity).

        # Example output object
        citations = [
            Citation(source="Law 1", text="Theft is punishable by hanging"),
            Citation(source="Law 2", text="Tax evasion is punishable by banishment."),
        ]

        output = Output(
            query=query_str, 
            response=response_text, 
            citations=citations
            )
        
        return output

        """
        query_engine = CitationQueryEngine.from_args(index=self.index, similarity_top_k=self.k)
        query_with_instructions = self.add_instructions(query_str)
        response = query_engine.query(query_with_instructions)
        citations = []
        for node in response.source_nodes:
            source_match = self.source_regex.match(node.text)
            source_num, text = (int(source_match.group('number')), source_match.group('text')) \
                if source_match else (None, node.text)
            citations.append(Citation(
                source=node.metadata.get("source") + " > " + node.metadata.get("section"),
                text=text,
                number=source_num
            ))

        return Output(
            query=query_str,
            response=response.response,
            citations=citations
        )

if __name__ == "__main__":
    # Example workflow
    doc_service = DocumentService()  # implemented
    print("Creating documents from PDFs...")
    doc_create_start_time = time.time()
    docs = doc_service.create_documents()  # implemented
    print(f"[{len(docs)}] Documents created in {time.time() - doc_create_start_time:.2f} seconds.")

    index = QdrantService()  # implemented
    print("Connecting to Qdrant...")
    index.connect()  # implemented
    print("Connection successful.")
    index.load(docs)  # implemented
    print("Documents loaded into Qdrant index.")

    query = "what happens if I steal?"
    print("Querying index: " + query)
    query_start_time = time.time()
    output = index.query(query)  # implemented
    print(f"Query completed in {time.time() - query_start_time:.2f} seconds.")
    print(output)

    query2_start_time = time.time()
    output2 = index.query("what are the penalties for tax evasion?")
    print(f"Query completed in {time.time() - query2_start_time:.2f} seconds.")
    print(output2)
