import asyncio
import io
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from PIL import Image, ImageOps

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

# Telegram can reject some otherwise-valid JPEG files with IMAGE_PROCESS_FAILED.
# Re-encode every image once at startup into a clean RGB JPEG and send the
# resulting bytes with BufferedInputFile instead of relying on Telegram to
# process the original file.
prepared_images: dict[str, bytes] = {}


def prepare_image(path: Path) -> bytes | None:
    if not path.exists():
        logger.error("Image does not exist: %s", path)
        return None

    try:
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source)
            if source.mode in ("RGBA", "LA"):
                background = Image.new("RGB", source.size, "white")
                background.paste(source, mask=source.getchannel("A"))
                image = background
            else:
                image = source.convert("RGB")

            output = io.BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=92,
                optimize=True,
                progressive=False,
            )
            data = output.getvalue()

        logger.info("Prepared image %s (%d bytes)", path, len(data))
        return data
    except Exception:
        logger.exception("Could not prepare image: %s", path)
        return None


def get_prepared_image(path: Path) -> BufferedInputFile | None:
    data = prepared_images.get(str(path))
    if not data:
        return None
    return BufferedInputFile(data, filename=path.stem + ".jpg")


async def send_withdrawal(user_id: int) -> None:
    index = rotation_index.get(user_id, 0)
    image = WITHDRAWAL_IMAGES[index % len(WITHDRAWAL_IMAGES)]
    photo = get_prepared_image(image)

    if photo is None:
        logger.error("Prepared withdrawal image is unavailable: %s", image)
        return

    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
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

    start_photo = get_prepared_image(START_IMAGE)
    if start_photo is None:
        await message.answer("Bot image is not configured correctly.")
        return

    # A fresh /start begins the rotation from the first withdrawal image.
    rotation_index[user_id] = 0

    try:
        await message.answer_photo(
            photo=start_photo,
            caption=START_CAPTION,
        )
    except Exception:
        logger.exception("Failed sending start image to %s", user_id)
        await message.answer("The start image could not be sent. Please try /start again.")
        return

    # First withdrawal is sent immediately, then every 2 hours.
    await send_withdrawal(user_id)
    schedule_user(user_id)


async def main() -> None:
    global bot

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    all_images = [START_IMAGE, *WITHDRAWAL_IMAGES]
    for image in all_images:
        prepared = prepare_image(image)
        if prepared:
            prepared_images[str(image)] = prepared

    missing = [str(path) for path in all_images if str(path) not in prepared_images]
    if missing:
        raise RuntimeError(
            "These configured images could not be prepared: " + ", ".join(missing)
        )

    bot = Bot(BOT_TOKEN)
    scheduler.start()

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
