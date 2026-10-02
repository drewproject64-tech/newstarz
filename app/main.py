import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
START_IMAGE = Path(os.getenv("START_IMAGE", "assets/start.jpg"))
WITHDRAWAL_IMAGES = [
    Path(os.getenv("WITHDRAWAL_IMAGE_1", "assets/withdrawal_257000.jpg")),
    Path(os.getenv("WITHDRAWAL_IMAGE_2", "assets/withdrawal_320000.jpg")),
    Path(os.getenv("WITHDRAWAL_IMAGE_3", "assets/withdrawal_239000.jpg")),
]

START_CAPTION = """🎁 250 TL ile Başla, 2.000 TL’ye Ulaş!
🔥 10 Dakikada Heyecanı Yaşa
💸 Fırsatı Kaçırma, Hemen Oyuna Kat!

https://strz.cc/CoxW"""

WITHDRAWAL_CAPTION = """Bu hafta sonu 1000$'a kadar kazanmanıza sadece bir saniye kaldı! Abonelerimizin bu tutarı yeni çektiğini görün, şimdi abone olun!"""

INTERVAL_SECONDS = 2 * 60 * 60

dp = Dispatcher()
bot: Bot | None = None
scheduler = AsyncIOScheduler()
rotation_index: dict[int, int] = {}
jobs: dict[int, object] = {}


async def send_withdrawal(user_id: int) -> None:
    index = rotation_index.get(user_id, 0)
    image = WITHDRAWAL_IMAGES[index % len(WITHDRAWAL_IMAGES)]

    if not image.exists():
        logger.error("Missing withdrawal image: %s", image)
        return

    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile(image),
            caption=WITHDRAWAL_CAPTION,
        )
        rotation_index[user_id] = (index + 1) % len(WITHDRAWAL_IMAGES)
    except Exception:
        logger.exception("Failed sending scheduled message to %s", user_id)


def schedule_user(user_id: int) -> None:
    existing = jobs.get(user_id)
    if existing:
        try:
            existing.remove()
        except Exception:
            pass

    job = scheduler.add_job(
        send_withdrawal,
        trigger=IntervalTrigger(seconds=INTERVAL_SECONDS),
        args=[user_id],
        id=f"user_{user_id}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    jobs[user_id] = job


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    user_id = message.from_user.id

    if not START_IMAGE.exists():
        await message.answer("Bot image is not configured yet.")
        return

    rotation_index[user_id] = 0

    await message.answer_photo(
        photo=FSInputFile(START_IMAGE),
        caption=START_CAPTION,
        parse_mode=ParseMode.HTML,
    )

    await send_withdrawal(user_id)
    schedule_user(user_id)


async def main() -> None:
    global bot
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    for image in [START_IMAGE, *WITHDRAWAL_IMAGES]:
        if not image.exists():
            logger.warning("Configured image does not exist yet: %s", image)

    bot = Bot(BOT_TOKEN)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
