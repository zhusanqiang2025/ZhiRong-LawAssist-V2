import os
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import json

# ================= 配置区 =================
# 从 Settings 获取 API 配置（统一使用 QWEN3_API_*）
from app.core.config import settings
API_KEY = settings.QWEN3_API_KEY
API_BASE_URL = settings.QWEN3_API_BASE
MODEL_NAME = settings.QWEN3_MODEL
# =========================================

class LegalDocument(BaseModel):
    """法律文档模型"""
    title: str = Field(description="文档标题")
    content: str = Field(description="文档内容")
    doc_type: str = Field(description="文档类型：法规、案例、合同模板等")
    jurisdiction: str = Field(description="管辖范围")
    effective_date: str = Field(description="生效日期")
    keywords: List[str] = Field(description="关键词列表")

class LegalSearchResult(BaseModel):
    """法律检索结果"""
    query: str = Field(description="用户查询")
    relevant_docs: List[LegalDocument] = Field(description="相关文档列表")
    summary: str = Field(description="检索结果摘要")
    legal_analysis: str = Field(description="法律分析")

class LegalRAGSystem:
    """法律检索增强生成系统"""

    def __init__(self, collection_name: str = "legal_docs"):
        # 初始化嵌入模型
        self.embeddings = OpenAIEmbeddings(
            api_key=API_KEY,
            model="text-embedding-3-small"
        )

        # 初始化向量数据库
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings
        )

        # 初始化LLM
        http_client = httpx.Client(verify=False, trust_env=False)
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            api_key=API_KEY,
            base_url=API_BASE_URL,
            temperature=0.1,
            http_client=http_client
        )

        # 初始化解析器
        self.parser = PydanticOutputParser(pydantic_object=LegalSearchResult)

        # 创建提示词模板
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", f"""你是一个专业的法律检索助手。请根据用户的问题和提供的法律文档，
            提供相关的法律依据和分析。

            {self.parser.get_format_instructions()}

            请确保引用的法律条文准确无误，分析具有针对性。"""),
            ("user", """用户问题：{query}

            相关法律文档：
            {context}

            请提供法律分析和建议。""")
        ])

        # 创建处理链
        self.chain = self.prompt | self.llm | self.parser

    def add_legal_document(self, doc: LegalDocument):
        """添加法律文档到向量数据库"""
        # 创建Document对象
        document = Document(
            page_content=doc.content,
            metadata={
                "title": doc.title,
                "doc_type": doc.doc_type,
                "jurisdiction": doc.jurisdiction,
                "effective_date": doc.effective_date,
                "keywords": doc.keywords
            }
        )

        # 添加到向量数据库
        self.vectorstore.add_documents([document])

    def search(self, query: str, k: int = 5) -> LegalSearchResult:
        """执行法律检索"""
        # 检索相关文档
        relevant_docs = self.vectorstore.similarity_search(query, k=k)

        # 将检索到的文档转换为LegalDocument对象
        legal_docs = []
        for doc in relevant_docs:
            legal_doc = LegalDocument(
                title=doc.metadata.get("title", ""),
                content=doc.page_content,
                doc_type=doc.metadata.get("doc_type", ""),
                jurisdiction=doc.metadata.get("jurisdiction", ""),
                effective_date=doc.metadata.get("effective_date", ""),
                keywords=doc.metadata.get("keywords", [])
            )
            legal_docs.append(legal_doc)

        # 使用LLM生成分析
        context = "\n\n".join([f"标题: {doc.title}\n内容: {doc.content}" for doc in legal_docs])

        result = self.chain.invoke({
            "query": query,
            "context": context
        })

        return result

# 示例法律文档数据
sample_law_docs = [
    LegalDocument(
        title="中华人民共和国劳动合同法",
        content="第九条 用人单位招用劳动者，不得扣押劳动者的居民身份证和其他证件，不得要求劳动者提供担保或者以其他名义向劳动者收取财物。",
        doc_type="法规",
        jurisdiction="全国",
        effective_date="2008-01-01",
        keywords=["劳动合同", "扣押证件", "收取财物"]
    ),
    LegalDocument(
        title="中华人民共和国劳动合同法",
        content="第二十三条 用人单位与劳动者可以在劳动合同中约定保守用人单位的商业秘密和与知识产权相关的保密事项。对负有保密义务的劳动者，用人单位可以在劳动合同或者保密协议中与劳动者约定竞业限制条款。",
        doc_type="法规",
        jurisdiction="全国",
        effective_date="2008-01-01",
        keywords=["竞业限制", "保密义务", "商业秘密"]
    ),
    LegalDocument(
        title="竞业限制案例",
        content="某科技公司与员工签订竞业限制协议，约定员工离职后2年内不得从事同类业务。后因公司未按约定支付竞业限制补偿金，员工提起诉讼。法院认定，用人单位未支付竞业限制补偿金超过三个月的，劳动者可请求解除竞业限制协议。",
        doc_type="案例",
        jurisdiction="北京",
        effective_date="2021-05-12",
        keywords=["竞业限制", "补偿金", "解除协议"]
    ),
    LegalDocument(
        title="技术服务合同模板",
        content="甲方委托乙方提供技术服务，服务期限为一年。乙方应按约定时间完成服务，甲方应按约定支付服务费用。任何一方违约，应承担违约责任。",
        doc_type="合同模板",
        jurisdiction="通用",
        effective_date="2023-01-01",
        keywords=["技术服务", "服务期限", "违约责任"]
    )
]

# 创建并初始化RAG系统
def create_legal_rag_system():
    rag_system = LegalRAGSystem()

    # 添加示例法律文档
    for doc in sample_law_docs:
        rag_system.add_legal_document(doc)

    return rag_system

# 示例用法
if __name__ == "__main__":
    rag_system = create_legal_rag_system()

    # 执行检索
    query = "员工签订竞业限制协议后，公司未支付竞业限制补偿金，员工是否还需要履行竞业限制义务？"
    result = rag_system.search(query)

    print("=== 法律检索结果 ===")
    print(f"查询: {result.query}")
    print(f"摘要: {result.summary}")
    print(f"法律分析: {result.legal_analysis}")
    print(f"相关文档数量: {len(result.relevant_docs)}")

    for i, doc in enumerate(result.relevant_docs):
        print(f"\n{i+1}. {doc.title}")
        print(f"   类型: {doc.doc_type}")
        print(f"   管辖: {doc.jurisdiction}")
        print(f"   内容: {doc.content[:100]}...")
