import logging
import structlog


def configure_logging(environment: str = "development") -> None:
    """Configure structlog-backed logging for API and workers."""

    renderer = (
        structlog.processors.JSONRenderer()
        if environment == "production"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
