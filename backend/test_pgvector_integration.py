# backend/test_pgvector_integration.py
"""
pgvector 集成测试脚本

验证 pgvector 扩展安装、数据库迁移、向量生成和搜索功能。
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import logging
from sqlalchemy import text
from app.database import SessionLocal
from app.core.config import settings
from app.services.contract_generation.rag.bge_client import get_bge_client
from app.services.contract_generation.rag.pgvector_store import get_pgvector_store
from app.models.contract_template import ContractTemplate

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PgVectorIntegrationTest:
    """pgvector 集成测试类"""

    def __init__(self):
        self.db = None
        self.results = {
            "tests": [],
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    def setup(self):
        """初始化测试环境"""
        try:
            self.db = SessionLocal()
            logger.info("✅ 数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False

    def teardown(self):
        """清理测试环境"""
        if self.db:
            self.db.close()
            logger.info("数据库连接已关闭")

    def record_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        self.results["tests"].append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        if passed:
            self.results["passed"] += 1
            logger.info(f"✅ {test_name}: {message}")
        else:
            self.results["failed"] += 1
            logger.error(f"❌ {test_name}: {message}")

    def test_pgvector_extension(self):
        """测试 pgvector 扩展是否安装"""
        test_name = "pgvector 扩展检查"
        try:
            result = self.db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            has_extension = result.fetchone() is not None

            if has_extension:
                self.record_test(test_name, True, "pgvector 扩展已安装")
                return True
            else:
                self.record_test(test_name, False, "pgvector 扩展未安装")
                return False
        except Exception as e:
            self.record_test(test_name, False, f"检查失败: {e}")
            return False

    def test_embedding_columns(self):
        """测试 embedding 相关字段是否存在"""
        test_name = "embedding 字段检查"
        try:
            # 查询表结构
            result = self.db.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'contract_templates'
                AND column_name IN ('embedding', 'embedding_updated_at', 'embedding_text_hash')
            """))
            columns = {row[0]: row[1] for row in result.fetchall()}

            missing = []
            if 'embedding' not in columns:
                missing.append('embedding')
            if 'embedding_updated_at' not in columns:
                missing.append('embedding_updated_at')
            if 'embedding_text_hash' not in columns:
                missing.append('embedding_text_hash')

            if missing:
                self.record_test(test_name, False, f"缺少字段: {', '.join(missing)}")
                return False
            else:
                self.record_test(test_name, True, f"所有字段存在: {list(columns.keys())}")
                return True
        except Exception as e:
            self.record_test(test_name, False, f"检查失败: {e}")
            return False

    def test_hnsw_index(self):
        """测试 HNSW 索引是否存在"""
        test_name = "HNSW 索引检查"
        try:
            result = self.db.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE indexname = 'idx_contract_templates_embedding_cosine'
            """))
            has_index = result.fetchone() is not None

            if has_index:
                self.record_test(test_name, True, "HNSW 索引已创建")
                return True
            else:
                self.record_test(test_name, False, "HNSW 索引不存在")
                return False
        except Exception as e:
            self.record_test(test_name, False, f"检查失败: {e}")
            return False

    def test_bge_service(self):
        """测试 BGE 嵌入服务"""
        test_name = "BGE 嵌入服务"
        try:
            bge_client = get_bge_client()
            test_text = "这是一个测试文本"
            result = bge_client.embed(test_text)

            if result.embedding and len(result.embedding) == 1024:
                self.record_test(test_name, True, f"BGE 服务正常, 嵌入维度: {len(result.embedding)}")
                return True
            else:
                self.record_test(test_name, False, f"嵌入维度错误: {len(result.embedding) if result.embedding else 0}")
                return False
        except Exception as e:
            self.record_test(test_name, False, f"BGE 服务异常: {e}")
            return False

    def test_vector_store(self):
        """测试向量存储服务"""
        test_name = "PgVectorStore 初始化"
        try:
            vector_store = get_pgvector_store()

            # 测试获取统计信息
            stats = vector_store.get_stats(self.db)

            self.record_test(
                test_name,
                True,
                f"总模板: {stats['total_templates']}, 已索引: {stats['indexed_templates']}, 覆盖率: {stats['coverage']}"
            )
            return True
        except Exception as e:
            self.record_test(test_name, False, f"初始化失败: {e}")
            return False

    def test_vector_search(self):
        """测试向量搜索功能"""
        test_name = "向量相似度搜索"
        try:
            vector_store = get_pgvector_store()

            # 执行搜索
            results = vector_store.search(
                db=self.db,
                query="劳动合同模板",
                top_k=5
            )

            if results:
                self.record_test(
                    test_name,
                    True,
                    f"搜索返回 {len(results)} 个结果, 最高相似度: {results[0].similarity:.4f}"
                )
                return True
            else:
                self.record_test(test_name, False, "搜索未返回结果")
                return False
        except Exception as e:
            self.record_test(test_name, False, f"搜索失败: {e}")
            return False

    def test_template_retriever(self):
        """测试模板检索器"""
        test_name = "TemplateRetriever 检索"
        try:
            from app.services.contract_generation.rag.template_retriever import get_template_retriever

            retriever = get_template_retriever()

            # 执行检索
            result = retriever.retrieve(
                query="劳动合同模板",
                top_k=5,
                use_rerank=False  # 暂不使用重排
            )

            if result and result.templates:
                self.record_test(
                    test_name,
                    True,
                    f"检索返回 {len(result.templates)} 个结果"
                )
                return True
            else:
                self.record_test(test_name, False, "检索未返回结果")
                return False
        except Exception as e:
            self.record_test(test_name, False, f"检索失败: {e}")
            return False

    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("测试摘要")
        print("="*60)
        print(f"总测试数: {len(self.results['tests'])}")
        print(f"通过: {self.results['passed']} ✅")
        print(f"失败: {self.results['failed']} ❌")
        print(f"通过率: {(self.results['passed'] / len(self.results['tests']) * 100):.1f}%")
        print("="*60)

        if self.results["errors"]:
            print("\n错误详情:")
            for error in self.results["errors"]:
                print(f"  - {error}")

        print("\n详细结果:")
        for test in self.results["tests"]:
            status = "✅" if test["passed"] else "❌"
            print(f"  {status} {test['name']}: {test['message']}")

        print("="*60)

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始 pgvector 集成测试...")

        if not self.setup():
            logger.error("测试环境初始化失败")
            return False

        # 运行测试
        self.test_pgvector_extension()
        self.test_embedding_columns()
        self.test_hnsw_index()
        self.test_bge_service()
        self.test_vector_store()
        self.test_vector_search()
        self.test_template_retriever()

        self.teardown()
        self.print_summary()

        return self.results["failed"] == 0


def main():
    """主函数"""
    print("\n" + "="*60)
    print("pgvector 集成测试")
    print("="*60 + "\n")

    tester = PgVectorIntegrationTest()
    success = tester.run_all_tests()

    if success:
        print("\n🎉 所有测试通过! pgvector 集成正常工作。")
        print("\n下一步:")
        print("  1. 在 router.py 中启用 RAG 路由")
        print("  2. 运行数据迁移脚本为现有模板生成向量")
        print("  3. 测试前端智能搜索功能")
    else:
        print("\n⚠️  部分测试失败,请检查上述错误并修复。")
        print("\n常见问题:")
        print("  - pgvector 扩展未安装: 运行 CREATE EXTENSION vector;")
        print("  - 字段缺失: 运行 alembic upgrade head")
        print("  - BGE 服务不可用: 检查 settings.BGE_EMBEDDING_API_URL")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
