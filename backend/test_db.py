from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings

def test_database_connection():
    """测试数据库连接"""
    try:
        # 使用与应用相同的数据库URL
        engine = create_engine(settings.DATABASE_URL)
        
        # 尝试连接
        with engine.connect() as connection:
            print("数据库连接成功!")
            # 执行一个简单的查询
            result = connection.execute("SELECT 1")
            print(f"查询结果: {result.fetchone()}")
        
        return True
    except SQLAlchemyError as e:
        print(f"数据库连接失败: {e}")
        return False
    except Exception as e:
        print(f"未知错误: {e}")
        return False

if __name__ == "__main__":
    test_database_connection()