import base64
import logging
import os

import requests

from platforms.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class WahaHandler(BaseHandler):
    platform_id = 1

    def __init__(self, page):
        super().__init__(page)

        self.base_url = os.environ.get(
            "WAHA_API_URL",
            "http://waha:3000"
        ).rstrip("/")

        self.session = "default"

        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": os.environ.get("WAHA_API_KEY", ""),
        }

    @property
    def platform_name(self):
        try:
            return self.page.platform.name
        except Exception:
            return "WhatsApp"

    # ------------------------------------------------------------------
    # Send Text
    # ------------------------------------------------------------------

    def send(self, recipient_id: str, text: str):
        if not text or not text.strip():
            return None

        payload = {
            "session": self.session,
            "chatId": recipient_id,
            "text": str(text),
        }

        return self._post_json(
            f"{self.base_url}/api/sendText",
            payload,
        )

    # ------------------------------------------------------------------
    # Send Image
    # ------------------------------------------------------------------

    def send_image(
        self,
        recipient_id: str,
        file_bytes: bytes,
        filename="ticket.png",
        mime_type="image/png",
    ):

        payload = {
            "session": self.session,
            "chatId": recipient_id,
            "file": {
                "mimetype": mime_type,
                "filename": filename,
                "data": base64.b64encode(file_bytes).decode("utf-8"),
            },
        }

        return self._post_json(
            f"{self.base_url}/api/sendImage",
            payload,
        )

    # ------------------------------------------------------------------
    # Send File
    # ------------------------------------------------------------------

    def send_file(
        self,
        recipient_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type="application/pdf",
    ):

        payload = {
            "session": self.session,
            "chatId": recipient_id,
            "file": {
                "mimetype": mime_type,
                "filename": filename,
                "data": base64.b64encode(file_bytes).decode("utf-8"),
            },
        }

        return self._post_json(
            f"{self.base_url}/api/sendFile",
            payload,
        )

    # ------------------------------------------------------------------
    # Typing
    # ------------------------------------------------------------------

    def send_typing(self, recipient_id: str):
        payload = {
            "session": self.session,
            "chatId": recipient_id,
        }

        return self._post_json(
            f"{self.base_url}/api/startTyping",
            payload,
        )

    # ------------------------------------------------------------------
    # Download Media
    # ------------------------------------------------------------------

    def download_media(self, media: dict, media_type="media"):
        """
        Download media from WAHA.

        WAHA sometimes returns:
            data -> base64
        or
            url -> localhost:3000

        Inside Docker localhost is wrong, so replace it with WAHA_API_URL.
        """

        try:

            if not media:
                return None

            # Already embedded as base64
            if media.get("data"):
                return base64.b64decode(media["data"])

            url = media.get("url")

            if not url:
                return None

            # Replace localhost with docker hostname
            url = url.replace(
                "http://localhost:3000",
                self.base_url,
            )

            url = url.replace(
                "http://127.0.0.1:3000",
                self.base_url,
            )

            logger.info("[WAHA DOWNLOAD] %s", url)

            timeout = 30 if media_type in ("pdf", "voice") else 15

            response = requests.get(
                url,
                headers=self.headers,
                timeout=timeout,
            )

            response.raise_for_status()

            return response.content

        except Exception:
            logger.exception(
                "[WAHA %s DOWNLOAD ERROR]",
                media_type.upper(),
            )
            return None

    # ------------------------------------------------------------------
    # Internal POST
    # ------------------------------------------------------------------

    def _post_json(self, url: str, payload: dict):

        try:

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30,
            )

            if response.status_code not in (200, 201):
                logger.error(
                    "[WAHA ERROR] status=%s body=%s",
                    response.status_code,
                    response.text,
                )

            return response

        except Exception:
            logger.exception("[WAHA ERROR]")
            return None

    # ------------------------------------------------------------------
    # Parse Message
    # ------------------------------------------------------------------

    def parse_message(self, payload, page_id):
        from parsers.waha import parse_waha_message

        return parse_waha_message(
            payload=payload,
            page_id=page_id,
            platform_id=self.platform_id,
            platform_name=self.platform_name,
        )