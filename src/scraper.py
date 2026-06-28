"""
Telegram Scraper for Ethiopian Medical Business Channels
=========================================================
Scrapes public Telegram channels and stores:
- Raw messages as JSON (partitioned by date): data/raw/telegram_messages/YYYY-MM-DD/channel.json
- Images: data/raw/images/{channel_name}/{message_id}.jpg
- Logs: logs/scrape_YYYY-MM-DD.log

Usage:
    python src/scraper.py --demo --path data --limit 50
    python src/scraper.py --path data --limit 500   # live Telegram auth
"""

import os
import json
import asyncio
import argparse
import logging
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.datalake import write_channel_messages_json, write_manifest

load_dotenv()

api_id_str = os.getenv("TELEGRAM_API_ID")
api_hash   = os.getenv("TELEGRAM_API_HASH")

TODAY = datetime.today().strftime("%Y-%m-%d")

DEFAULT_CHANNEL_DELAY = 3.0
DEFAULT_MESSAGE_DELAY = 0.5

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("telegram_scraper")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, f"scrape_{TODAY}.log"), encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# =============================================================================
# LIVE SCRAPING (requires Telegram auth)
# =============================================================================

async def scrape_channel(client, channel, base_path, date_str,
                         limit=100, message_delay=DEFAULT_MESSAGE_DELAY,
                         channel_delay=DEFAULT_CHANNEL_DELAY, max_retries=3):
    from telethon.tl.types import MessageMediaPhoto
    from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError

    channel_name = channel.strip("@")
    retries = 0

    while True:
        try:
            entity = await client.get_entity(channel)
            channel_title = entity.title
            messages = []

            channel_image_dir = os.path.join(base_path, "raw", "images", channel_name)
            os.makedirs(channel_image_dir, exist_ok=True)

            logger.info(f"Starting scrape of {channel} (limit={limit})")

            async for message in client.iter_messages(entity, limit=limit):
                image_path: Optional[str] = None
                has_media = message.media is not None

                if has_media and isinstance(message.media, MessageMediaPhoto):
                    filename  = f"{message.id}.jpg"
                    image_path = os.path.join(channel_image_dir, filename)
                    try:
                        await client.download_media(message.media, image_path)
                    except Exception as e:
                        logger.warning(f"Failed to download image for message {message.id}: {e}")
                        image_path = None

                message_dict = {
                    "message_id":    message.id,
                    "channel_name":  channel_name,
                    "channel_title": channel_title,
                    "message_date":  message.date.isoformat(),
                    "message_text":  message.message or "",
                    "has_media":     has_media,
                    "image_path":    image_path,
                    "views":         message.views or 0,
                    "forwards":      message.forwards or 0,
                }
                messages.append(message_dict)

                if message_delay and message_delay > 0:
                    await asyncio.sleep(message_delay)

            write_channel_messages_json(
                base_path=base_path, date_str=date_str,
                channel_name=channel_name, messages=messages,
            )

            logger.info(f"Finished scraping {channel}: {len(messages)} messages saved")
            if channel_delay and channel_delay > 0:
                await asyncio.sleep(channel_delay)
            return len(messages)

        except FloodWaitError as e:
            wait_seconds = max(int(getattr(e, "seconds", 0) or 0), 1)
            logger.warning(f"FloodWaitError for {channel}: sleeping {wait_seconds}s")
            await asyncio.sleep(wait_seconds)
            retries += 1
            if retries > max_retries:
                logger.error(f"Too many FloodWait retries for {channel}. Skipping.")
                return 0

        except ChannelPrivateError:
            logger.error(f"Channel {channel} is private or inaccessible. Skipping.")
            return 0

        except UsernameNotOccupiedError:
            logger.error(f"Channel {channel} does not exist. Skipping.")
            return 0

        except Exception as e:
            logger.error(f"Error scraping {channel}: {e}")
            return 0


async def scrape_all_channels(client, channels, base_path, limit=100,
                              message_delay=DEFAULT_MESSAGE_DELAY,
                              channel_delay=DEFAULT_CHANNEL_DELAY):
    await client.start()
    logger.info(f"Client authenticated. Scraping {len(channels)} channels...")

    os.makedirs(os.path.join(base_path, "raw", "telegram_messages", TODAY), exist_ok=True)
    os.makedirs(os.path.join(base_path, "raw", "images"), exist_ok=True)

    stats         = {}
    channel_counts = {}

    for channel in channels:
        logger.info(f"Scraping {channel}...")
        count = await scrape_channel(
            client, channel, base_path, TODAY, limit,
            message_delay, channel_delay,
        )
        stats[channel]                    = count
        channel_counts[channel.strip("@")] = count

    write_manifest(base_path=base_path, date_str=TODAY,
                   channel_message_counts=channel_counts)

    total = sum(stats.values())
    logger.info(f"Scraping complete. Total messages: {total}")
    for ch, count in stats.items():
        logger.info(f"  {ch}: {count} messages")
    return stats


# =============================================================================
# DEMO MODE — realistic medical/pharmaceutical sample data
# =============================================================================

SAMPLE_MESSAGES = {
    "CheMed123": {
        "title": "CheMed Medical Supplies",
        "posts": [
            ("Paracetamol 500mg tablets available in bulk. Min order 1000 units. Contact us for wholesale pricing. #MedicalSupplies", True),
            ("New stock: Amoxicillin 250mg/5ml suspension. Branded and generic available. Nationwide delivery across Ethiopia.", False),
            ("Insulin pens (Novo Nordisk) back in stock. Limited quantity. DM for pricing. #Diabetes #MedSupply", True),
            ("Blood pressure monitors (Omron HEM-7120) at competitive prices. Warranty included. Same-day dispatch available.", True),
            ("Hiring: experienced pharmacist for our Bole branch. Send CV to our email. Salary negotiable.", False),
            ("Surgical gloves (latex & nitrile) all sizes. Boxes of 100. Bulk discount for clinics and hospitals.", True),
            ("Reminder: always verify expiry dates. We guarantee fresh stock with 18+ months validity on all products.", False),
            ("Azithromycin 500mg in stock. Prescription required. Contact our licensed pharmacist for consultation.", True),
            ("Medical oxygen cylinders for home use. Rental and purchase options. 24hr emergency delivery available.", False),
            ("Digital thermometers and pulse oximeters now in stock. Essential home health monitoring tools. DM for pricing.", True),
            ("Metformin 850mg tablets for diabetes management. 30-day supply packs. Consult your doctor before purchase.", False),
            ("We stock WHO-approved medicines only. All products sourced from licensed Ethiopian pharmaceutical importers.", True),
            ("Wound care supplies: bandages, antiseptic solutions, sterile dressings. Hospital and clinic bulk orders welcome.", False),
            ("Vitamin D3 and Calcium supplements now available. Important for bone health especially for elderly patients.", True),
            ("Branches open 7 days a week, 8AM-9PM. Emergency pharmacist line available 24 hours.", False),
            ("Hydrocortisone cream 1% for skin conditions. Available OTC. Consult pharmacist for proper usage guidance.", True),
            ("Contraceptive supplies fully stocked: pills, injectables, implants. Confidential service available.", False),
            ("Eye drops (artificial tears, antibiotic) in stock. Multiple brands. Prescription items require valid Rx.", True),
            ("Pediatric medicines restocked: ORS sachets, Zinc tablets, children's paracetamol syrup. Child care kit available.", False),
            ("Thank you for 10,000 followers! Committed to affordable, quality healthcare products for all Ethiopians.", True),
        ],
    },
    "lobelia4cosmetics": {
        "title": "Lobelia Cosmetics & Health",
        "posts": [
            ("New arrival: Neutrogena Hydro Boost Water Gel. Perfect for Ethiopian climate. SPF 25 included. Limited stock!", True),
            ("Natural Ethiopian shea butter — 100% organic, unrefined. Amazing for skin and hair. 500g jars available.", True),
            ("IMPORTANT: avoid skin creams containing mercury or high-dose hydroquinone. Always check product ingredients.", False),
            ("Cetaphil Gentle Skin Cleanser — dermatologist recommended for sensitive skin. Available in 250ml and 500ml.", True),
            ("Argan oil from Morocco now available. Excellent for hair and skin care. Authentic with quality certificates.", False),
            ("Baby care corner: Johnson's Baby range, Mustela, and natural alternatives fully stocked.", True),
            ("Did you know? Ethiopian kesso extract has natural antibacterial properties beneficial for skin health.", False),
            ("Vitamin C serums restocked: The Ordinary, Garnier, and local brands. Great for skin brightening & anti-aging.", True),
            ("Sunscreen reminder: SPF 30+ is essential at Addis Ababa's high altitude. Options for all budgets available.", False),
            ("Bioderma Sensibio H2O micellar water — gentle makeup remover for sensitive skin. Customer favourite!", True),
            ("Hair care special: Ethiopian castor oil + biotin shampoo combo. Fight hair loss naturally. 20% off this week.", True),
            ("We only stock EFDA-approved products. Ethiopian Food and Drug Authority certification is our standard.", False),
            ("Rosewater toner — 100% natural, alcohol-free. Ideal for toning and refreshing skin. Local & imported brands.", True),
            ("Eczema care: Aveeno, CeraVe, and prescription-strength options available. Consult our skin specialist.", False),
            ("Collagen supplements (capsules & powder) now available. Support joint health and skin elasticity.", True),
            ("Acne treatment kit: salicylic acid cleanser + benzoyl peroxide + oil-free moisturiser. Bundle deal this week!", True),
            ("Natural henna for hair colouring — safe alternative to chemical dyes. Various shades available in store.", False),
            ("Makeup hygiene tip: replace mascara every 3 months. Affordable replacements from top brands in stock.", True),
            ("Moringa oil — Ethiopia's superfood for skin. Anti-inflammatory, rich in oleic acid. 50ml bottles in stock.", False),
            ("Customer review: 'My skin has never looked better since your recommended routine.' Thank you for trusting us!", True),
        ],
    },
    "tikvahpharma": {
        "title": "Tikvah Pharma Ethiopia",
        "posts": [
            ("Tikvah Pharma distributes WHO-prequalified medicines across Ethiopia. Serving hospitals, clinics and pharmacies.", False),
            ("Tender announcement: Ministry of Health procurement for ARV medications. Deadline: 15 July 2026. Details below.", True),
            ("Quality alert: counterfeit Coartem (antimalarial) reported in market. Only buy from licensed distributors.", False),
            ("Our cold chain facility in Addis ensures vaccine integrity from manufacturer to clinic. ISO certified storage.", True),
            ("Cancer medicines available: Tamoxifen, Methotrexate, Cyclophosphamide. Hospital orders only. Contact us.", False),
            ("Partnering with UNICEF Ethiopia to distribute essential medicines to rural health centres in Oromia region.", True),
            ("Good Manufacturing Practice (GMP) training for pharmacy staff. Next session: July 10. Register via our website.", False),
            ("Antifungal medications fully stocked: Fluconazole, Itraconazole, Clotrimazole. All dosage forms available.", True),
            ("Expanding: new distribution centre opening in Hawassa to serve Southern Ethiopia regions.", True),
            ("TB medicines update: full first-line regimen (HRZE) available. Supporting the national TB elimination programme.", False),
            ("Pharmacovigilance: report any adverse drug reactions to EFDA. Patient safety is everyone's responsibility.", False),
            ("Oxytocin and Misoprostol for maternal health — fully stocked. Supporting safe motherhood across Ethiopia.", True),
            ("Point-of-care diagnostic kits: Malaria, HIV, Hepatitis B rapid tests. For remote health facilities.", True),
            ("Continuing education webinar: rational drug use — this Friday 3PM. Free for all healthcare professionals.", False),
            ("Surgical supplies arrived: sutures, surgical mesh, staples. Contract with ALERT Hospital renewed 2026-2027.", True),
            ("Ethiopia's pharmaceutical sector growing at 12% annually. Tikvah Pharma proud to support local industry.", False),
            ("Hypertension medicines: Amlodipine, Lisinopril, Atenolol — all available in 28-day blister packs.", True),
            ("Storage reminder: keep medicines in cool, dry places away from sunlight. Ask your pharmacist for guidance.", False),
            ("Mental health medicines now available: antidepressants and antipsychotics. Stigma-free consultation offered.", True),
            ("Tikvah Pharma wins 'Best Pharmaceutical Distributor 2026' award from EPSA. Thank you for your trust!", True),
        ],
    },
}

CHANNEL_COLORS = {
    "CheMed123":         (30,  80, 160),
    "lobelia4cosmetics": (160, 40, 100),
    "tikvahpharma":      (20, 120,  60),
}


def _create_placeholder_image(path: str, channel_name: str = "",
                               msg_id: int = 0, text_snippet: str = "") -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Pillow not installed — write a minimal valid JPEG placeholder
        with open(path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9")
        return

    bg  = CHANNEL_COLORS.get(channel_name, (60, 60, 60))
    img = Image.new("RGB", (400, 300), bg)
    draw = ImageDraw.Draw(img)

    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except OSError:
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    draw.text((20, 20), f"@{channel_name}",   fill="white",         font=font_lg)
    draw.text((20, 55), f"Message #{msg_id}", fill=(200, 200, 200), font=font_sm)

    words = text_snippet[:120].split()
    lines, line = [], ""
    for w in words:
        if len(line + " " + w) > 40:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        lines.append(line)

    y = 100
    for ln in lines[:5]:
        draw.text((20, y), ln, fill=(220, 220, 220), font=font_sm)
        y += 22

    draw.text((20, 270), "DEMO IMAGE", fill=(255, 255, 255), font=font_sm)
    img.save(path, "JPEG", quality=85)


def run_demo(base_path: str, limit: int) -> None:
    logger.info("[DEMO MODE] Generating sample medical/pharmaceutical data")

    date_str       = TODAY
    channel_counts = {}
    now            = datetime.now(timezone.utc)

    for channel_name, channel_data in SAMPLE_MESSAGES.items():
        channel_title = channel_data["title"]
        posts         = channel_data["posts"][:limit]
        messages      = []

        channel_image_dir = os.path.join(base_path, "raw", "images", channel_name)
        os.makedirs(channel_image_dir, exist_ok=True)

        logger.info(f"[DEMO] Scraping @{channel_name} (limit={limit})")

        for i, (text, has_media) in enumerate(posts):
            msg_id   = 1000 + i
            msg_date = (now - timedelta(hours=i * 4 + random.randint(0, 3))).isoformat()
            image_path = None

            if has_media:
                image_path = os.path.join(channel_image_dir, f"{msg_id}.jpg")
                _create_placeholder_image(image_path, channel_name, msg_id, text)

            views    = random.randint(100, 10000)
            forwards = random.randint(0, views // 8)

            msg = {
                "message_id":    msg_id,
                "channel_name":  channel_name,
                "channel_title": channel_title,
                "message_date":  msg_date,
                "message_text":  text,
                "has_media":     has_media,
                "image_path":    image_path,
                "views":         views,
                "forwards":      forwards,
            }
            messages.append(msg)

        write_channel_messages_json(
            base_path=base_path, date_str=date_str,
            channel_name=channel_name, messages=messages,
        )
        channel_counts[channel_name] = len(messages)
        logger.info(f"[DEMO] Finished @{channel_name}: {len(messages)} messages saved")

    write_manifest(base_path=base_path, date_str=date_str,
                   channel_message_counts=channel_counts)

    total = sum(channel_counts.values())
    logger.info(f"[DEMO] Complete. Total messages: {total}")
    for ch, count in channel_counts.items():
        logger.info(f"  @{ch}: {count} messages")
    logger.info(f"[DEMO] Data lake: {base_path}/raw/")
    logger.info(f"[DEMO] Log file: logs/scrape_{date_str}.log")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Telegram Scraper for Ethiopian Medical Business Channels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/scraper.py --demo --path data --limit 20
    python src/scraper.py --path data --limit 500
        """
    )
    parser.add_argument("--path",          type=str,   default="data")
    parser.add_argument("--limit",         type=int,   default=100)
    parser.add_argument("--message-delay", type=float, default=DEFAULT_MESSAGE_DELAY)
    parser.add_argument("--channel-delay", type=float, default=DEFAULT_CHANNEL_DELAY)
    parser.add_argument("--demo",          action="store_true",
                        help="Generate sample data without Telegram auth")
    args = parser.parse_args()

    if args.demo:
        run_demo(args.path, args.limit)
    else:
        if not api_id_str or not api_hash:
            print("ERROR: Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env file")
            sys.exit(1)

        from telethon import TelegramClient
        api_id = int(api_id_str)
        client = TelegramClient("session/telegram_session", api_id, api_hash)
        logger.info("Telegram client initialized")

        target_channels = [
            "@CheMed123",
            "@lobelia4cosmetics",
            "@tikvahpharma",
        ]

        async def main():
            async with client:
                await scrape_all_channels(
                    client, target_channels, args.path, args.limit,
                    message_delay=args.message_delay,
                    channel_delay=args.channel_delay,
                )

        asyncio.run(main())