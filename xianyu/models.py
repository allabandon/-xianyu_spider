import logging

from tortoise import Model, Tortoise, fields

logger = logging.getLogger(__name__)


class XianyuProduct(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(description="商品标题")
    price = fields.CharField(max_length=50, description="当前售价")
    area = fields.CharField(max_length=100, description="发货地区")
    seller = fields.CharField(max_length=100, description="卖家昵称")
    link = fields.TextField(description="商品链接")
    link_hash = fields.CharField(max_length=32, unique=True, description="商品链接哈希")
    image_url = fields.TextField(description="商品图片链接")
    publish_time = fields.DatetimeField(null=True, description="发布时间")

    class Meta:
        table = "xianyu_products"


class ChatMessage(Model):
    id = fields.IntField(pk=True)
    conversation_id = fields.CharField(max_length=128, db_index=True, description="会话 ID")
    sender_id = fields.CharField(max_length=64, default="", description="发送者 ID")
    sender_name = fields.CharField(max_length=128, default="", description="发送者昵称")
    text = fields.TextField(description="文本内容")
    direction = fields.CharField(max_length=8, default="in", description="in / out")
    source = fields.CharField(max_length=16, default="", description="user / gateway，给 agent 对账")
    raw_json = fields.TextField(null=True, description="原始推送")
    created_at = fields.DatetimeField(auto_now_add=True, description="入库时间")

    class Meta:
        table = "im_messages"


async def ensure_im_schema() -> list[str]:
    """旧表用 content/replied，新模型用 text/source。generate_schemas 不会改已有表。"""
    conn = Tortoise.get_connection("default")
    try:
        _, rows = await conn.execute_query("PRAGMA table_info(im_messages)")
    except Exception:
        return []
    names = {row[1] for row in rows}
    if not names:
        return []
    if "text" in names and "source" in names and "content" not in names:
        return []
    text_expr = "text" if "text" in names else "content" if "content" in names else "''"
    source_expr = "source" if "source" in names else "''"
    await conn.execute_script(
        f"""
        CREATE TABLE im_messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            conversation_id VARCHAR(128) NOT NULL,
            sender_id VARCHAR(64) NOT NULL DEFAULT '',
            sender_name VARCHAR(128) NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            direction VARCHAR(8) NOT NULL DEFAULT 'in',
            source VARCHAR(16) NOT NULL DEFAULT '',
            raw_json TEXT,
            created_at TIMESTAMP NOT NULL
        );
        INSERT INTO im_messages_new
            (id, conversation_id, sender_id, sender_name, text, direction, source, raw_json, created_at)
        SELECT
            id, conversation_id, sender_id, sender_name, {text_expr}, direction, {source_expr}, raw_json, created_at
        FROM im_messages;
        DROP TABLE im_messages;
        ALTER TABLE im_messages_new RENAME TO im_messages;
        CREATE INDEX IF NOT EXISTS idx_im_messages_conversation_id ON im_messages (conversation_id);
        """
    )
    logger.info("im_messages 已从旧结构迁移到 text/source")
    return ["rebuild im_messages"]
