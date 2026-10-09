from celery import Celery

from app.core.config import settings


def get_broker_url() -> str:
    if settings.REDIS_HOST:
        password = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
        port = settings.REDIS_PORT or "6379"
        return f"redis://{password}{settings.REDIS_HOST}:{port}/0"
    return "memory://"


broker_url = get_broker_url()
celery_app = Celery("app.worker", broker=broker_url, backend=broker_url)
celery_app.conf.task_default_queue = "main-queue"


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"
