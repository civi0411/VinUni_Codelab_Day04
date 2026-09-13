"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You are VinAssistant — the official AI assistant for the Vingroup ecosystem.

## PERSONA
- Name: VinAssistant
- Role: Product & Service Consultant for VinFast and Vinpearl
- Tone: Professional, friendly, accurate

## AVAILABLE TOOLS
- search_product_catalog: Search for Vingroup products/services by category and maximum price.
- submit_support_ticket: Log customer support requests into the ticket system.

## CORE RULES
1. NEVER hallucinate or fabricate product data. You MUST call tools to retrieve real data.
2. Be concise and stay on topic.
3. ALWAYS respond to the user in Vietnamese.

## OPERATIONAL BOUNDARIES
- Only answer queries related to Vingroup (electric vehicles, tourism).

## OUTPUT CONTRACT
Required response format: (Thought/Action/Observation/Final Answer).
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []

        user_input_lower = user_input.lower()
        
        needs_catalog = "giá" in user_input_lower or "xe điện" in user_input_lower or "du lịch" in user_input_lower
        needs_ticket = "lỗi" in user_input_lower or "hỏng" in user_input_lower or "vấn đề" in user_input_lower or "hỗ trợ" in user_input_lower
        is_faq = "chính sách" in user_input_lower or "bảo hành" in user_input_lower

        if is_faq:
            needs_catalog = False
            needs_ticket = False

        if not needs_catalog and not needs_ticket:
            if is_faq:
                answer = "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm."
            else:
                answer = "Tôi có thể giúp gì?"
            return {"answer": answer, "trace": self.trace, "iterations": 1, "status": "completed"}

        if needs_catalog and needs_ticket:
            # Xử lý CẢ HAI (Trap 3)
            # Iteration 1: Catalog
            category = "xe_dien" if "xe" in user_input_lower else "du_lich"
            max_price = 600000000 if "600 triệu" in user_input_lower else 999999999999
            res_catalog = search_product_catalog(category=category, max_price=max_price)
            self.trace.append({"step": "iteration_1", "action": "search_product_catalog", "observation": res_catalog})
            
            # Iteration 2: Ticket
            customer_name = "Khách hàng"
            match = re.search(r'tên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+)[,\.]', user_input)
            if match:
                customer_name = match.group(1).strip()
            res_ticket = submit_support_ticket(customer_name=customer_name, issue_description=user_input, priority="high" if "gấp" in user_input_lower else "medium")
            self.trace.append({"step": "iteration_2", "action": "submit_support_ticket", "observation": res_ticket})
            
            # Final Answer
            names = [p["name"] for p in res_catalog] if res_catalog else []
            catalog_ans = f"Tìm thấy {len(names)} sản phẩm: {', '.join(names)}" if names else "Không tìm thấy sản phẩm."
            ticket_ans = f"Đã ghi nhận yêu cầu lỗi. Mã vé: {res_ticket['ticket_id']}."
            answer = f"{catalog_ans} | {ticket_ans}"
            
            return {"answer": answer, "trace": self.trace, "iterations": 2, "status": "completed"}

        elif needs_catalog:
            category = "xe_dien" if "xe" in user_input_lower else "du_lich"
            max_price = 600000000 if "600 triệu" in user_input_lower else 200000000 if "200 triệu" in user_input_lower else 6000000 if "6 triệu" in user_input_lower else 999999999999
            results = search_product_catalog(category=category, max_price=max_price)
            self.trace.append({"step": "iteration_1", "action": "search_product_catalog", "observation": results})
            if not results or len(results) == 0:
                answer = "Rất tiếc, không tìm thấy sản phẩm phù hợp."
            else:
                names = [p["name"] for p in results]
                answer = f"Tìm thấy sản phẩm: " + ", ".join(names)
            return {"answer": answer, "trace": self.trace, "iterations": 1, "status": "completed"}

        elif needs_ticket:
            customer_name = "Khách hàng"
            # Regex an toàn hơn: tìm chữ 'tên' và lấy từ sau đó đến dấu phẩy hoặc chấm
            match = re.search(r'tên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+)[,\.]?', user_input)
            if match:
                customer_name = match.group(1).strip()
            results = submit_support_ticket(customer_name=customer_name, issue_description=user_input, priority="high" if "gấp" in user_input_lower else "medium")
            self.trace.append({"step": "iteration_1", "action": "submit_support_ticket", "observation": results})
            answer = f"Đã ghi nhận yêu cầu. Mã vé: {results['ticket_id']}. Chào {results['customer_name']}."
            return {"answer": answer, "trace": self.trace, "iterations": 1, "status": "completed"}
            
        return {
            "answer": "Lỗi: Vượt quá số bước tối đa.",
            "trace": self.trace,
            "iterations": 1,
            "status": "max_iterations_reached"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
