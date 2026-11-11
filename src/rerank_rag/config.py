from pathlib import Path
import os
from dotenv import load_dotenv
#模型路径
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
#数据路径
DATA_DIR = PROJECT_ROOT / "data"
#加载.env
load_dotenv(PROJECT_ROOT / ".env")

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

#文档切分
CHUNK_SIZE = 220
CHUNK_OVERLAP = 40
EMBED_BATCH_SIZE = 20

#数据库路径
CHROMA_DIR = Path(
    os.getenv(
        "CHROMA_DIR",
        str(PROJECT_ROOT / "chroma_db"),
    )
)

COLLECTION_NAME = "retrieve_and_rerank_bge_base_zh"


BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
EMBEDDING_MODEL_PATH = Path(
    os.getenv(
        "LOCAL_EMBED_MODEL_PATH",
        str(PROJECT_ROOT / "models" / "bge-base-zh-v1.5"),
    )
)

RERANK_MODEL_PATH = Path(
    os.getenv(
        "LOCAL_RERANK_MODEL_PATH",
        str(PROJECT_ROOT / "models" / "bge-reranker-base"),
    )
)
RERANK_CANDIDATE_K = 20
RERANK_TOP_N = 5
RERANK_BATCH_SIZE = 8
