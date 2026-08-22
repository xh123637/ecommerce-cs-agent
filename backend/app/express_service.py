"""快递100 即时查询物流服务。"""

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from .config import KUAI100_CUSTOMER, KUAI100_KEY, KUAI100_QUERY_URL

COURIER_ALIASES = {
    "顺丰": "shunfeng",
    "顺丰速运": "shunfeng",
    "中通": "zhongtong",
    "圆通": "yuantong",
    "韵达": "yunda",
    "申通": "shentong",
    "极兔": "jtexpress",
    "德邦": "debrandt",
    "京东": "jd",
    "京东物流": "jd",
    "邮政": "youzhengguo",
    "中国邮政": "youzhengguo",
    "ems": "ems",
    "百世": "huitongkuaidi",
    "天天": "ttkd",
}

LEGACY_CODE_MAP = {
    "SF": "shunfeng",
    "ZTO": "zhongtong",
    "YTO": "yuantong",
    "YD": "yunda",
    "STO": "shentong",
    "JTSD": "jtexpress",
    "DBL": "debrandt",
    "JD": "jd",
    "YZPY": "youzhengguo",
    "EMS": "ems",
    "HTKY": "huitongkua",
    "TTKD": "ttkd",
}


def normalize_shipper_code(code: str) -> str:
    """把旧快递鸟编码或中文名归一成快递100编码。"""
    code = (code or "").strip()
    if not code:
        return ""
    key = code.upper()
    return LEGACY_CODE_MAP.get(key, COURIER_ALIASES.get(code, key))


def _data_sign(request_data: dict, key: str, customer: str = "") -> str:
    param = json.dumps(request_data, ensure_ascii=False)
    source = param
    if customer:
        source += customer
    source += key
    return hashlib.md5(source.encode("utf-8")).hexdigest().upper()


def _post_query(request_data: dict) -> dict:
    if not KUAI100_KEY:
        return {"error": "快递100未配置，请检查 KUAI100_KEY"}
    param = json.dumps(request_data, ensure_ascii=False)
    sign_source = param
    if KUAI100_CUSTOMER:
        sign_source += KUAI100_KEY
        sign_source += KUAI100_CUSTOMER
    else:
        sign_source += KUAI100_KEY
    sign = hashlib.md5(sign_source.encode("utf-8")).hexdigest().upper()
    body = {
        "param": param,
        "sign": sign,
    }
    if KUAI100_CUSTOMER:
        body["customer"] = KUAI100_CUSTOMER
    data = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(KUAI100_QUERY_URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def query_express(shipper_code: str, tracking_no: str) -> dict:
    """查询真实物流轨迹。"""
    if not tracking_no:
        return {"error": "缺少快递单号"}
    com = normalize_shipper_code(shipper_code)
    if not com:
        return {"error": "缺少快递公司编码"}
    result = _post_query({"com": com, "num": tracking_no})
    if not isinstance(result, dict):
        return {"result": result}
    if result.get("status") != "200":
        return {
            **result,
            "success": False,
            "error": result.get("message") or result.get("msg") or "查询失败",
        }
    traces = []
    for item in result.get("data", []) or []:
        traces.append(
            {
                "AcceptTime": item.get("ftime") or item.get("time"),
                "AcceptStation": item.get("context"),
                "status": item.get("status", ""),
            }
        )
    return {
        "success": True,
        "state": result.get("state"),
        "com": result.get("com"),
        "nu": result.get("nu"),
        "Traces": traces,
        "raw": result,
    }


def extract_shipping(text: str) -> Optional[dict]:
    """从文本里粗识别常见快递公司和运单号。"""
    if not text:
        return None
    pattern = r"(?P<shipper>顺丰速运|顺丰|中通|圆通|韵达|申通|极兔|德邦|京东物流|京东|EMS|中国邮政|邮政|百世|天天)(?P<no>[0-9A-Za-z]{10,32})"
    match = re.search(pattern, text.upper() if re.search(r"[A-Za-z]", text) else text, re.IGNORECASE)
    if not match:
        return None
    shipper = match.group("shipper")
    code = normalize_shipper_code(shipper)
    return {"shipper": shipper, "shipper_code": code, "tracking_no": match.group("no")}


def query_ticket_express(ticket: dict) -> dict:
    """优先用工单已填快递字段查询物流，缺失时从描述中识别。"""
    blob = (
        f"{ticket.get('title') or ''} "
        f"{ticket.get('description') or ''} "
        f"{ticket.get('resolution') or ''}"
    )
    shipping = None
    if ticket.get("shipper_code") and ticket.get("tracking_no"):
        shipping = {
            "shipper": ticket.get("shipper_code"),
            "shipper_code": normalize_shipper_code(str(ticket.get("shipper_code"))),
            "tracking_no": ticket.get("tracking_no"),
        }
    else:
        shipping = extract_shipping(blob)
    if not shipping or not shipping.get("tracking_no"):
        return {
            "error": "未能从工单中识别到快递公司和运单号",
            "ticket_id": ticket.get("id"),
        }
    data = query_express(shipping["shipper_code"], shipping["tracking_no"])
    data["shipper"] = shipping.get("shipper")
    data["shipper_code"] = shipping["shipper_code"]
    data["tracking_no"] = shipping["tracking_no"]
    data["ticket_id"] = ticket.get("id")
    return data
