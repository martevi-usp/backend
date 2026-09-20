from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the host (backend ADR-0006).

    Not `/healthz`: Cloud Run's front end reserves that path and answers it
    itself, so it never reaches the container.

    Deliberately touches nothing: no provider call (the Smithsonian DEMO_KEY
    throttle would mark the service unhealthy and trigger restart loops), no
    database, no translation model. It answers as soon as the process is up.
    """
    return {"status": "ok"}
