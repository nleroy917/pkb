import polars as pl
import pymupdf

from tqdm import tqdm
from sentence_transformers import SentenceTransformer

CHUNK_SIZE = 500
OVERLAP_SIZE = 50

model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")
library = pl.read_csv("library.csv")
library_parsed = (library
    .filter(pl.col("File Attachments").str.contains(".pdf"))
    .with_columns(
        pl.col("File Attachments").str.split(";").list.eval(
            pl.element().str.strip_chars().filter(pl.element().str.ends_with(".pdf"))
        ).list.first().str.split("/").list.last().alias("pdf_file_name")
    )
)

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF.
    """
    doc = pymupdf.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap_size: int = OVERLAP_SIZE) -> list[str]:
    """
    Chunk text into smaller pieces with specified chunk size and overlap.
    """
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(text[start:end])
        start += chunk_size - overlap_size
    return chunks

# extract all text from PDF, store as long string, save to parquet
pdf_texts = []
for row in tqdm(library_parsed.iter_rows(named=True), desc="Extracting PDF Text", total=library_parsed.height):
    pdf_file_name = row["pdf_file_name"]
    pdf_path = f"pdfs/{pdf_file_name}"
    text = extract_text_from_pdf(pdf_path)
    pdf_texts.append({"key": row["Key"], "text": text})

# save to parquet
pl.DataFrame(pdf_texts).write_parquet("datasets/pdf_texts.parquet")

# iterate over each PDF file in the library
# chunk and embed with the model
# store in dictionary with key to original citation/document + chunk text + embedding
embeddings_dicts = []
for row in tqdm(library_parsed.iter_rows(named=True), desc="Processing PDFs", total=library_parsed.height):
    pdf_file_name = row["pdf_file_name"]
    key = row["Key"]
    pdf_path = f"pdfs/{pdf_file_name}"
    # extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    # chunk the text
    chunks = chunk_text(text)
    # embed each chunk and store in dictionary
    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        embeddings_dicts.append({
            "chunk_id": f"{key}_chunk_{i}",
            "key": key,
            "chunk_text": chunk,
            "embedding": embedding
        })

# create dataframe, store in "datasets/all_minilm_l6_v2.parquet"
embeddings_df = pl.DataFrame(embeddings_dicts)
embeddings_df.write_parquet("datasets/all_minilm_l6_v2.parquet")