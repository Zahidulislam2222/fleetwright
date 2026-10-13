"""Run the standalone local application using the central configuration boundary."""

import uvicorn

from fw_agent.app import create_app
from fw_core.settings import AgentAppSettings, load


def main() -> None:
    settings = load(AgentAppSettings)
    uvicorn.run(
        create_app(settings),
        host=settings.agent.host,
        port=settings.agent.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
