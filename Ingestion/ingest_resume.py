import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import shutil

load_dotenv()

def ingest_all_documents(directory_path: str):

    persist_db_path = "./chroma_db"
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    all_splits = []

    print(f"开始扫描文件夹: {directory_path}...")
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)

        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif filename.endswith(".docx") or filename.endswith(".doc"):
                loader = UnstructuredWordDocumentLoader(file_path)
            elif filename.endswith(".txt"):
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                continue

            print(f"正在处理: {filename}")
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = text_splitter.split_documents(documents)
            all_splits.extend(splits)

        except Exception as e:
            print(f"处理 {filename} 时出错: {e}")

    if not all_splits:
        print("未发现可处理的文档。")
        return

    if os.path.exists("./chroma_db"):
        shutil.rmtree("./chroma_db")
        print("已清理旧的数据库...")

    print(f"正在将 {len(all_splits)} 个片段存入数据库...")

    vectorstore = Chroma.from_documents(
        documents=all_splits,
        embedding=embeddings,
        persist_directory=persist_db_path,
        collection_name="resume_info"
    )
    print(f"成功！所有简历已存入 {persist_db_path}")


if __name__ == "__main__":
    # 把所有的 pdf 和 docx 文件都放在这个文件夹里,向量数据库默认为覆盖
    ingest_all_documents(".")