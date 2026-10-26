"""历史部署的兼容边界；界面与新配置统一使用 Vocove。"""
import os


# 既有云端文件和离线客户端依赖这些协议值，不能随显示品牌更换。
DRIVE_APP_ID = "drive-vocabulary-book-v1"
DRIVE_BATCH_PREFIX = "vocabulary-"


def getenv(name: str, default: str = "") -> str:
    """新变量即使显式为空也优先，旧变量仅用于未迁移的启动配置。"""
    if not name.startswith("VOCOVE_"):
        raise ValueError("环境变量需使用 VOCOVE_ 前缀")
    if name in os.environ:
        return os.environ[name]
    previous = ("VOCABULARY_CJK_FONT" if name == "VOCOVE_CJK_FONT"
                else "VOCAB_" + name.removeprefix("VOCOVE_"))
    return os.environ.get(previous, default)
