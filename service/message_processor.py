import os
import uuid
import requests
from graph.agent_graph import get_agent_graph
from graph.agent_response import AgentResponse
from graph.utils import count_request
from software_services.client_services import ClientService
from ocr.processor import process_prescription_ocr

class IncomingMessage:
    def __init__(self, sender_id, page_id, platform_id, msg_type,
                 text=None, media=None, platform_name=None):
        self.sender_id     = sender_id
        self.page_id       = page_id
        self.platform_id   = platform_id
        self.platform_name = platform_name
        self.type          = msg_type
        self.text          = text
        self.media         = media


def _calc_total_usage(result: dict) -> dict:
    nodes = [
        "intent_usage",
        "lab_info_usage",
        "booking_usage",
        "complaint_usage",
        "direct_usage",
        "inquiry_usage",
    ]
    total_in = total_out = total = 0
    breakdown = {}

    for key in nodes:
        u = result.get(key) or {}
        i = u.get("input_tokens",  0) or 0
        o = u.get("output_tokens", 0) or 0
        t = u.get("total_tokens",  0) or 0
        if i or o:
            breakdown[key] = {"input": i, "output": o, "total": t or i + o}
            total_in  += i
            total_out += o
            total     += t or i + o

    return {
        "breakdown":    breakdown,
        "total_input":  total_in,
        "total_output": total_out,
        "total_tokens": total,
    }


def run_agent(message: IncomingMessage) -> tuple[str, bytes | None]:
    client = ClientService.get_or_create_client(
        message.sender_id, message.page_id, message.platform_id
    )

    platform_name = message.platform_name or str(message.platform_id)

    state = {
        "page_id":           message.page_id,
        "sender_id":         message.sender_id,
        "platform_id":       message.platform_id,
        "platform_name":     platform_name,
        "user_message":      message.text or "",
        "summary":           client.summary          or "",
        "last_bot_message":  client.last_bot_message or "",
        "intent":            None,
        "response":          None,
        "intent_usage":      None,
        "lab_info_usage":    None,
        "booking_usage":     None,
        "complaint_usage":   None,
        "direct_usage":      None,   
        "inquiry_usage":     None,
        "booking_saved":     None,
        "complaint_saved":   None,
        "inquiry_saved":     None,
    }

    try:
        result       = get_agent_graph().invoke(state)
        response_obj = AgentResponse.from_result(result)
    except Exception as e:
        print(f"[run_agent] Error: {e}")
        return "Sorry, something went wrong. Please try again in a moment.", None

    usage = _calc_total_usage(result)
    print(
        f"\n📊 TOTAL USAGE"
        f" | intent={result.get('intent')}"
        f" | in={usage['total_input']}"
        f" | out={usage['total_output']}"
        f" | total={usage['total_tokens']}"
    )
    for node, u in usage["breakdown"].items():
        print(f"   └─ {node:<22} in={u['input']:>5} | out={u['output']:>5} | total={u['total']:>6}")

    # Return reply text and any booking PDF generated
    return response_obj.response, result.get("booking_pdf")


def handle_image_message(message: IncomingMessage, page) -> tuple[str, bytes | None]:
    """
    Downloads the prescription image, processes classification and OCR extraction,
    and returns a reply response (and optional PDF) to send back to the user.
    """
    image_url = message.media.get("url") if message.media else None
    if not image_url:
        return "برجاء إرسال صورة روشتة صالحة.", None

    try:
        print(f"[handle_image_message] Downloading image: {image_url}")
        img_res = requests.get(image_url, timeout=30)
        if img_res.status_code == 200:
            # Ensure static/uploads exists
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            uploads_dir = os.path.join(project_dir, "static", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}.jpg"
            image_path = os.path.join(uploads_dir, filename)
            with open(image_path, "wb") as f:
                f.write(img_res.content)

            # Process image OCR classification & extraction
            ocr_result = process_prescription_ocr(
                image_path=image_path,
                phone_number="",
                comes_from=f"Facebook:{message.sender_id}:{message.page_id}",
                laboratory_id=page.laboratory_id
            )


            if ocr_result.get("success"):
                # High confidence prescription -> Send extracted text to LangGraph Agent
                extracted_text = ocr_result.get("extracted_text", "")
                message.text = f"[Prescription OCR Extracted Text]:\n{extracted_text}"
                message.type = "text"
                return run_agent(message)
            else:
                # Low confidence prescription or spam
                if ocr_result.get("classified_as") == "prescription":
                    static_reply = "لقد استلمنا صورتك وسيقوم الطبيب بمراجعتها والرد عليك ."
                    
                    # Update Client summary in DB
                    ClientService.update_client_summary_and_last_bot_message(
                        sender_id=message.sender_id,
                        page_id=message.page_id,
                        platform_id=message.platform_id,
                        summary="User uploaded a prescription image. Waiting for manual doctor review on dashboard.",
                        last_bot_message=static_reply
                    )
                    count_request()
                    return static_reply, None
                else:
                    spam_reply = "عذراً، يبدو أن الصورة المرفقة ليست روشتة طبية واضحة. يرجى إرسال صورة روشتة صحيحة لطلب التحاليل."
                    return spam_reply, None
        else:
            return "عذرًا، فشل تحميل الصورة المرفقة. يرجى المحاولة مرة أخرى.", None
    except Exception as e:
        print(f"[handle_image_message] Error: {e}")
        return "عذرًا، حدث خطأ أثناء معالجة الصورة المرفقة. يرجى المحاولة مرة أخرى.", None
