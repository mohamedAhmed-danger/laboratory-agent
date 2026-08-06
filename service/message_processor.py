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



# Pricing per model (USD per token)
OCR_INPUT_COST_PER_TOKEN   = 0.3  / 1_000_000
OCR_OUTPUT_COST_PER_TOKEN  = 2.5  / 1_000_000

FLASH_INPUT_COST_PER_TOKEN  = 0.25 / 1_000_000
FLASH_OUTPUT_COST_PER_TOKEN = 1.5  / 1_000_000


def _calc_total_usage(result: dict, ocr_usage: dict = None) -> dict:
    """
    Pure calculation — takes the agent graph result (+ optional OCR usage)
    and returns token/cost breakdown. No DB/subscription side effects here;
    that happens in run_agent() once `usage` actually exists.
    """
    nodes = [
        ("ocr_vision_usage", ocr_usage),
        ("intent_usage", result.get("intent_usage")),
        ("lab_info_usage", result.get("lab_info_usage")),
        ("booking_usage", result.get("booking_usage")),
        ("complaint_usage", result.get("complaint_usage")),
        ("direct_usage", result.get("direct_usage")),
        ("inquiry_usage", result.get("inquiry_usage")),
    ]

    total_in = total_out = total = 0
    total_cost_usd = 0.0
    breakdown = {}

    for key, u in nodes:
        if not u:
            continue
        i = u.get("input_tokens",  0) or 0
        o = u.get("output_tokens", 0) or 0
        t = u.get("total_tokens",  0) or (i + o)

        if not (i or o):
            continue

        # Pick pricing based on which model produced this usage
        if key == "ocr_vision_usage":
            in_rate, out_rate = OCR_INPUT_COST_PER_TOKEN, OCR_OUTPUT_COST_PER_TOKEN
        else:
            in_rate, out_rate = FLASH_INPUT_COST_PER_TOKEN, FLASH_OUTPUT_COST_PER_TOKEN

        node_cost = (i * in_rate) + (o * out_rate)

        breakdown[key] = {
            "input": i,
            "output": o,
            "total": t,
            "cost_usd": node_cost,
        }

        total_in  += i
        total_out += o
        total     += t
        total_cost_usd += node_cost   # accumulate cost directly, since rates differ per node

    total_cost_cents = total_cost_usd * 100
    req_per_dollar = int(1.0 / total_cost_usd) if total_cost_usd > 0 else 0

    return {
        "breakdown":        breakdown,
        "total_input":      total_in,
        "total_output":     total_out,
        "total_tokens":     total,
        "total_cost_usd":   total_cost_usd,
        "total_cost_cents": total_cost_cents,
        "req_per_dollar":   req_per_dollar,
    }


def _consume_subscription(message: "IncomingMessage", usage: dict) -> None:
    """
    Deducts one message + the real estimated cost from the laboratory's
    subscription, based on the page this message came in on.
    Silently no-ops if the page/subscription can't be resolved, so a
    billing lookup failure never breaks the reply to the user.
    """
    from software_services.subscription_service import SubscriptionService
    from models.models import Page

    try:
        page = Page.query.filter_by(
            page_id=message.page_id,
            platform_id=message.platform_id,
        ).first()

        if not page:
            print(f"[_consume_subscription] No page found for page_id={message.page_id} platform_id={message.platform_id}")
            return

        subscription = SubscriptionService.get_by_page(page)

        if not subscription:
            print(f"[_consume_subscription] No subscription found for laboratory_id={page.laboratory_id}")
            return

        SubscriptionService.consume(
            subscription,
            cost=usage["total_cost_usd"],
        )

    except Exception as e:
        print(f"[_consume_subscription] Error: {e}")


def run_agent(message: IncomingMessage, ocr_usage: dict = None) -> tuple[str, bytes | None]:
    client = ClientService.get_or_create_client(
        message.sender_id,
        message.page_id,
        message.platform_id
    )

    print("=" * 80)
    print("RUN_AGENT")
    print("Platform :", message.platform_id)
    print("Page     :", message.page_id)
    print("Sender   :", message.sender_id)
    print("Client   :", client)
    print("=" * 80)

    if client is None:
        raise RuntimeError(
            f"ClientService returned None "
            f"(platform={message.platform_id}, "
            f"page={message.page_id}, "
            f"sender={message.sender_id})"
        )

    platform_name = message.platform_name or str(message.platform_id)

    state = {
        "page_id": message.page_id,
        "sender_id": message.sender_id,
        "platform_id": message.platform_id,
        "platform_name": platform_name,
        "user_message": message.text or "",
        "summary": client.summary or "",
        "last_bot_message": client.last_bot_message or "",

        "intent": None,
        "refined_queries": [],

        "rag_context": "",
        "search_results": [],
        "top_score": 0.0,

        "response": None,

        "intent_usage": None,
        "lab_info_usage": None,
        "booking_usage": None,
        "complaint_usage": None,
        "direct_usage": None,
        "inquiry_usage": None,

        "booking_saved": None,
        "complaint_saved": None,
        "inquiry_saved": None,
    }

    try:
        result = get_agent_graph().invoke(state)
        response_obj = AgentResponse.from_result(result)
    except Exception as e:
        print(f"[run_agent] Error: {e}")
        from notified_center.EmailSender import send_production_alert
        send_production_alert(
            subject="Agent Graph Execution Failure in message_processor",
            body_or_error=e,
            context={"sender_id": message.sender_id, "page_id": message.page_id, "platform_id": message.platform_id}
        )
        return "Sorry, something went wrong. Please try again in a moment.", None

    usage = _calc_total_usage(result, ocr_usage=ocr_usage)

    # Deduct usage from the laboratory's subscription now that `usage` exists.
    _consume_subscription(message, usage)

    print("\n" + "=" * 76)
    print(" ⚡ REAL-TIME REQUEST METRICS & COST ANALYSIS")
    print(ocr_usage)
    print(f" 👤 Sender ID: {message.sender_id} | Platform: {platform_name} | Intent: {result.get('intent')}")
    print("-" * 76)
    print(" 🔹 Node Breakdown:")
    for node, u in usage["breakdown"].items():
        print(f"    └─ {node:<22} in={u['input']:>5} | out={u['output']:>5} | total={u['total']:>6} | cost=${u['cost_usd']:.8f}")
    print("-" * 76)
    print(" 📊 TOTAL REAL REQUEST METRICS:")
    print(f"    - Input Tokens  : {usage['total_input']:,}")
    print(f"    - Output Tokens : {usage['total_output']:,}")
    print(f"    - Total Tokens  : {usage['total_tokens']:,}")
    print(f"    - Real Cost     : ${usage['total_cost_usd']:.8f} USD ({usage['total_cost_cents']:.5f}¢ cents)")
    if usage['req_per_dollar'] > 0:
        print(f"    - Capacity      : ~{usage['req_per_dollar']:,} such real requests per $1.00 USD")
    print("=" * 76 + "\n", flush=True)

    # Return reply text and any booking PDF generated
    return response_obj.response, result.get("booking_ticket")


def handle_image_message(message: IncomingMessage, page) -> tuple[str, bytes | None]:
    """
    Downloads the prescription image, processes classification and OCR extraction,
    and returns a reply response (and optional PDF) to send back to the user.
    """

    image_bytes = None

    try:
        # =========================
        # WhatsApp
        # =========================
        if (message.platform_name or "").lower() == "whatsapp":
            from platforms.waha_handler import WahaHandler

            handler = WahaHandler(page)
            image_bytes = handler.download_media(message.media, "image")

            if not image_bytes:
                return "عذرًا، فشل تحميل الصورة المرفقة. يرجى المحاولة مرة أخرى.", None

        # =========================
        # Facebook / Messenger
        # =========================
        else:
            image_url = message.media.get("url") if message.media else None

            if not image_url:
                return "برجاء إرسال صورة روشتة صالحة.", None

            print(f"[handle_image_message] Downloading image: {image_url}")

            img_res = requests.get(image_url, timeout=30)

            if img_res.status_code != 200:
                return "عذرًا، فشل تحميل الصورة المرفقة. يرجى المحاولة مرة أخرى.", None

            image_bytes = img_res.content

        # ====================================
        # Save image
        # ====================================

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(project_dir, "static", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.jpg"
        image_path = os.path.join(uploads_dir, filename)

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # ====================================
        # OCR
        # ====================================

        ocr_result = process_prescription_ocr(
            image_path=image_path,
            phone_number="",
            comes_from=f"{message.platform_name}:{message.sender_id}:{message.page_id}",
            laboratory_id=page.laboratory_id,
        )

        ocr_usage = ocr_result.get("ocr_usage")

        if ocr_result.get("success"):
            extracted_text = ocr_result.get("extracted_text", "")
            message.text = f"[Prescription OCR Extracted Text]:\n{extracted_text}"
            return run_agent(message, ocr_usage=ocr_usage)

        if ocr_result.get("classified_as") == "prescription":
            static_reply = (
                "لقد استلمنا صورتك وسيقوم الطبيب بمراجعتها والرد عليك."
            )

            ClientService.update_client_summary_and_last_bot_message(
                sender_id=message.sender_id,
                page_id=message.page_id,
                platform_id=message.platform_id,
                summary="User uploaded a prescription image. Waiting for manual doctor review on dashboard.",
                last_bot_message=static_reply,
            )

            count_request()
            return static_reply, None

        return (
            "عذراً، يبدو أن الصورة المرفقة ليست روشتة طبية واضحة. يرجى إرسال صورة روشتة صحيحة لطلب التحاليل.",
            None,
        )

    except Exception as e:
        print(f"[handle_image_message] Error: {e}")

        from notified_center.EmailSender import send_production_alert

        send_production_alert(
            subject="Image Processing Failure in message_processor",
            body_or_error=e,
            context={
                "sender_id": message.sender_id,
                "page_id": message.page_id,
                "platform_id": message.platform_id,
            },
        )

        return (
            "عذرًا، حدث خطأ أثناء معالجة الصورة المرفقة. يرجى المحاولة مرة أخرى.",
            None,
        )