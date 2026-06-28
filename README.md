# Medical Telegram Data Warehouse

An end-to-end ELT data pipeline that scrapes Ethiopian medical business Telegram channels, transforms the data into a star-schema warehouse using dbt, enriches it with YOLOv8 object detection, and exposes insights through a FastAPI analytical API, all orchestrated with Dagster.


## Architecture

Telegram Channels
      │
      ▼
[Telethon Scraper] ──► data/raw/  (JSON Data Lake + Images)
      │
      ▼
[load_to_postgres.py] ──► PostgreSQL: raw.telegram_messages
      │
      ▼
[dbt] ──► staging.stg_telegram_messages
       ──► marts.dim_channels
       ──► marts.dim_dates
       ──► marts.fct_messages
      │
      ▼
[YOLOv8] ──► marts.fct_image_detections
      │
      ▼
[FastAPI] ──► REST API endpoints
      │
      ▼
[Dagster] ──► Scheduled pipeline orchestration

## Data Sources

| Channel | URL | Type |
|---|---|---|
| CheMed | https://t.me/CheMed123 | Medical products |
| Lobelia Cosmetics | https://t.me/lobelia4cosmetics | Cosmetics & health |
| Tikvah Pharma | https://t.me/tikvahpharma | Pharmaceuticals |
| Additional | https://et.tgstat.com/medicine | Mixed medical |


## Project Structure


medical-telegram-warehouse/
├── .github/workflows/unittests.yml   # CI pipeline
├── .env.example                      # Environment variable template
├── .gitignore
├── docker-compose.yml                # PostgreSQL + pgAdmin
├── Dockerfile
├── requirements.txt
├── README.md
├── data/
│   └── raw/
│       ├── telegram_messages/        # Partitioned JSON data lake
│       │   └── YYYY-MM-DD/
│       │       └── {channel}.json
│       └── images/                   # Downloaded channel images
│           └── {channel_name}/
│               └── {message_id}.jpg
├── logs/                             # Scraper and loader logs
├── medical_warehouse/                # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_telegram_messages.sql
│   │   │   └── schema.yml
│   │   └── marts/
│   │       ├── dim_channels.sql
│   │       ├── dim_dates.sql
│   │       ├── fct_messages.sql
│   │       └── schema.yml
│   └── tests/
│       ├── assert_no_future_messages.sql
│       └── assert_positive_views.sql
├── src/
│   ├── scraper.py                    # Telegram scraping pipeline
│   ├── load_to_postgres.py           # Data lake → PostgreSQL loader
│   └── yolo_detect.py               # YOLOv8 image enrichment
├── api/
│   ├── main.py                       # FastAPI application
│   ├── database.py                   # DB connection
│   └── schemas.py                    # Pydantic models
└── tests/                            # Python unit tests



## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/medical-telegram-warehouse.git
cd medical-telegram-warehouse
```

### 2. Configure Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:


TELEGRAM_API_ID=your_api_id        # from https://my.telegram.org
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+251XXXXXXXXX

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=medical_warehouse


### 3. Start PostgreSQL

```bash
docker-compose up -d
```

PostgreSQL will be available at `localhost:5432`.
pgAdmin UI is available at `http://localhost:5050` (admin@admin.com / admin).

### 4. Install Python Dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click **API development tools**
4. Create an application and copy `api_id` and `api_hash` into `.env`


## Running the Pipeline

### Task 1: Scrape Telegram Channels

```bash
python src/scraper.py
```

Scraped data is saved to:
- `data/raw/telegram_messages/YYYY-MM-DD/{channel}.json`
- `data/raw/images/{channel}/{message_id}.jpg`
- `logs/scraper_YYYY-MM-DD.log`

### Task 2: Load to PostgreSQL and Run dbt

```bash
# Load raw data into PostgreSQL
python src/load_to_postgres.py

# Navigate to the dbt project
cd medical_warehouse

# Test the database connection
dbt debug

# Run all models
dbt run

# Run all tests
dbt test

# Generate and serve documentation
dbt docs generate
dbt docs serve



## Star Schema Design

         dim_channels          dim_dates
         ─────────────         ──────────────
         channel_key (PK)      date_key (PK)
         channel_name          full_date
         channel_type          day_of_week
         first_post_date       day_name
         last_post_date        week_of_year
         total_posts           month
         avg_views             month_name
                               quarter
              │                year
              │                is_weekend
              │                    │
              └──────┬─────────────┘
                     │
               fct_messages
               ─────────────────
               message_id (PK)
               channel_key (FK)
               date_key (FK)
               message_text
               message_length
               views
               forwards
               has_media
               has_image
               image_path


**Design decisions:**
- Star schema chosen over snowflake for query simplicity on analytical workloads.
- `dim_dates` generated from actual message dates (no pre-generated calendar needed).
- Surrogate keys on `dim_channels` decouple the fact table from source channel names.


## dbt Tests

| Test Type | Applied To |
|---|---|
| `unique` + `not_null` | All primary keys |
| `not_null` | All foreign keys and critical columns |
| `relationships` | `channel_key` and `date_key` in `fct_messages` |
| `accepted_values` | `channel_type` in `dim_channels` |
| Custom: `assert_no_future_messages` | `stg_telegram_messages` |
| Custom: `assert_positive_views` | `stg_telegram_messages` |


## Environment Variable Reference

| Variable | Description | Required |
|---|---|---|
| `TELEGRAM_API_ID` | Telegram API app ID | Yes |
| `TELEGRAM_API_HASH` | Telegram API app hash | Yes |
| `TELEGRAM_PHONE` | Your phone number (with country code) | Yes |
| `POSTGRES_HOST` | Database hostname | Yes |
| `POSTGRES_PORT` | Database port (default: 5432) | Yes |
| `POSTGRES_USER` | Database username | Yes |
| `POSTGRES_PASSWORD` | Database password | Yes |
| `POSTGRES_DB` | Database name | Yes |
