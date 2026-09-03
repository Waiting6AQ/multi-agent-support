"""
种子数据

负责插入模拟数据（DML），与 Schema 定义分离。
"""
import sqlite3
from langchain_chroma import Chroma
from langchain_core.documents import Document


# ==================== FAQ 数据 ====================

FAQ_ENTRIES = [
    {
        "question": "蓝牙连接不上怎么办",
        "answer": "请尝试以下步骤：1) 重新启动设备蓝牙 2) 检查设备电量是否充足 3) 删除配对记录后重新配对 4) 确保设备在有效连接范围内（10米以内）。如仍无法解决，请联系人工客服。",
        "category": "连接问题",
    },
    {
        "question": "设备充电很慢或无法充电",
        "answer": "建议使用原装充电器和数据线。请检查充电接口是否有灰尘或异物，尝试更换充电线或充电头。如果充电指示灯不亮且已排除配件问题，可能是电池故障，建议送修检测。",
        "category": "充电问题",
    },
    {
        "question": "如何进行软件更新",
        "answer": "打开设备配套的 APP，进入「设置」→「设备信息」→「固件版本」，点击「检查更新」，按照提示完成更新。更新过程中请保持设备电量充足且不要断开蓝牙连接。",
        "category": "软件更新",
    },
    {
        "question": "退货政策是什么",
        "answer": "我们支持 7 天无理由退货（商品完好、包装完整）。30 天内出现非人为质量问题可申请换货。退换货请保留购买凭证、完整包装及配件。退款将在收到退货后 3-5 个工作日内原路返回。",
        "category": "售后服务",
    },
    {
        "question": "设备无法开机",
        "answer": "请长按电源键 15 秒以上尝试强制重启。若仍无反应，连接充电器等待 10 分钟后重试（电池可能过度放电）。如充电指示灯不亮且长按无效，可能是硬件故障，建议联系售后检修。",
        "category": "电源问题",
    },
    {
        "question": "如何恢复出厂设置",
        "answer": "进入设备设置 →「系统」→「重置」→「恢复出厂设置」。注意：此操作会清除设备上所有个人数据，请提前备份重要信息。重置完成后需要重新与手机配对。",
        "category": "系统问题",
    },
]


# ==================== 业务数据 ====================

ORDERS = [
    {
        "id": "ORD001",
        "product": "智能手表 Pro",
        "price": 1299.00,
        "status": "已发货",
        "shipping": "顺丰快递",
        "tracking": "SF1234567890",
        "estimated_delivery": "预计 2-3 天送达",
    },
    {
        "id": "ORD002",
        "product": "无线耳机 Max",
        "price": 599.00,
        "status": "处理中",
        "shipping": "圆通快递",
        "tracking": "YT9876543210",
        "estimated_delivery": "预计 3-5 天送达",
    },
    {
        "id": "ORD003",
        "product": "便携充电宝",
        "price": 199.00,
        "status": "已签收",
        "shipping": "顺丰快递",
        "tracking": "SF1122334455",
        "estimated_delivery": "已送达",
    },
]

PRODUCTS = [
    {
        "name": "智能手表 Pro",
        "category": "穿戴设备",
        "price": 1299.00,
        "features": '["心率监测", "血氧检测", "GPS定位", "NFC支付", "IP68防水", "14天续航"]',
        "stock": 156,
        "rating": 4.8,
    },
    {
        "name": "无线耳机 Max",
        "category": "音频",
        "price": 599.00,
        "features": '["主动降噪", "空间音频", "蓝牙5.3", "30小时续航", "IPX5防水"]',
        "stock": 89,
        "rating": 4.6,
    },
    {
        "name": "便携充电宝",
        "category": "电源",
        "price": 199.00,
        "features": '["20000mAh", "65W快充", "Type-C双向", "LED电量显示", "轻薄机身"]',
        "stock": 234,
        "rating": 4.5,
    },
    {
        "name": "智能音箱",
        "category": "智能家居",
        "price": 399.00,
        "features": '["语音助手", "Hi-Fi音质", "智能家居控制", "多房间联动", "蓝牙+WiFi"]',
        "stock": 67,
        "rating": 4.4,
    },
]


# ==================== 插入函数 ====================

def seed_faq(chroma_persist_dir: str, embeddings) -> None:
    """将 FAQ 写入 ChromaDB，已有数据则跳过"""
    store = Chroma(
        persist_directory=chroma_persist_dir,
        embedding_function=embeddings,
    )
    existing = store.get()
    if existing and existing.get("ids") and len(existing["ids"]) > 0:
        print(f"ℹ️  FAQ 向量库已有 {len(existing['ids'])} 条数据，跳过初始化")
        return

    docs = []
    for entry in FAQ_ENTRIES:
        docs.append(Document(
            page_content=entry["question"],
            metadata={
                "answer": entry["answer"],
                "category": entry["category"],
            },
        ))
    store.add_documents(docs)
    print(f"✅ FAQ 向量库初始化完成，共 {len(docs)} 条")


def seed_orders(db_path: str) -> None:
    """插入订单模拟数据，已有数据则跳过"""
    conn = sqlite3.connect(db_path)
    existing = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    if existing > 0:
        print(f"ℹ️  orders 表已有 {existing} 条数据，跳过初始化")
        conn.close()
        return

    for o in ORDERS:
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            (o["id"], o["product"], o["price"], o["status"],
             o["shipping"], o["tracking"], o["estimated_delivery"]),
        )
    conn.commit()
    conn.close()
    print(f"✅ orders 表初始化完成，共 {len(ORDERS)} 条")


def seed_products(db_path: str) -> None:
    """插入产品模拟数据，已有数据则跳过"""
    conn = sqlite3.connect(db_path)
    existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if existing > 0:
        print(f"ℹ️  products 表已有 {existing} 条数据，跳过初始化")
        conn.close()
        return

    for p in PRODUCTS:
        conn.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
            (p["name"], p["category"], p["price"], p["features"], p["stock"], p["rating"]),
        )
    conn.commit()
    conn.close()
    print(f"✅ products 表初始化完成，共 {len(PRODUCTS)} 条")
