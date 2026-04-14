import json
import logging
from datetime import datetime, timezone

import redis

from app.config import settings

logger = logging.getLogger(__name__)


def publish_profile_updated(user_id: int) -> bool:
    payload = {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.publish("profile_updated", json.dumps(payload))
        client.close()
        return True
    except Exception:
        logger.warning("Failed to publish profile_updated event", exc_info=True)
        return False
