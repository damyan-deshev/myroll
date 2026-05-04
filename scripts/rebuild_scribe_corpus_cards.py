#!/usr/bin/env python
from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.db.engine import get_engine
from backend.app.db.models import Campaign
from backend.app.settings import Settings
from backend.app.scribe_corpus import rebuild_campaign_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild derived Scribe corpus cards.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--campaign", help="Campaign id to rebuild")
    scope.add_argument("--all", action="store_true", help="Rebuild all campaigns")
    args = parser.parse_args()

    settings = Settings.from_env()
    factory = sessionmaker(bind=get_engine(settings), autoflush=False, expire_on_commit=False)
    with factory() as db:
        if args.all:
            campaign_ids = list(db.scalars(select(Campaign.id).order_by(Campaign.id)))
        else:
            campaign_ids = [args.campaign]
        for campaign_id in campaign_ids:
            with db.begin():
                count = rebuild_campaign_corpus(db, str(campaign_id))
            print(f"{campaign_id}: rebuilt {count} cards")


if __name__ == "__main__":
    main()
