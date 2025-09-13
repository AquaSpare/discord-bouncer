import logfire

from mybot.bot import main


def setup_observability():
    logfire.configure()
    logfire.instrument_pydantic_ai()
    logfire.instrument_sqlite3()
    logfire.instrument_aiohttp_client()


if __name__ == "__main__":
    import asyncio

    setup_observability()

    asyncio.run(main())
