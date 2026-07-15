#!/usr/bin/env python3

from digital_ic_agent.agent import (
    CommandRunner,
    DigitalICAgent,
    TargetHandler,
    create_agent,
    main,
)


__all__ = [
    "CommandRunner",
    "DigitalICAgent",
    "TargetHandler",
    "create_agent",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
